"""Genera las plantillas finales en dist/: incrusta el código de las Lambdas y de las pruebas."""
import json, os, pathlib
R = pathlib.Path(__file__).parent

def indentar(s, n):
    return "\n".join((" " * n + l) if l.strip() else "" for l in s.splitlines())

p = (R / "plantillas/principal.yaml").read_text()
for marca, f in (("@@VALIDAR@@", "validar.py"), ("@@EMITIR@@", "emitir_url.py")):
    code = (R / "lambdas" / f).read_text()
    assert len(code) < 4096, f
    p = p.replace(marca, indentar(code, 10))
(R / "dist/1-principal.yaml").write_text(p)

# ---------- generador de carga (JSON: sin conflictos con ${} de JavaScript)
archivos = {f"/opt/poc/pruebas/{n}": (R / "pruebas" / n).read_text() for n in ("comun.js", "carga.js", "seguridad.js", "generar_archivos.sh")}
archivos["/opt/poc/correr.sh"] = """#!/bin/bash
# Uso: sudo /opt/poc/correr.sh individual | pico | seguridad
set -euo pipefail
source /opt/poc/env
cd /opt/poc/pruebas
case "${1:-}" in
  individual|pico) k6 run --log-format raw -e ESCENARIO="$1" -e API_URL="$API_URL" -e API_KEY="$API_KEY" carga.js ;;
  seguridad) k6 run --log-format raw -e API_URL="$API_URL" -e API_KEY="$API_KEY" seguridad.js ;;
  *) echo "uso: $0 individual|pico|seguridad"; exit 1 ;;
esac
"""
partes = ["#!/bin/bash\nset -euo pipefail\nmkdir -p /opt/poc/pruebas /opt/poc/resultados /opt/poc/datos\n"]
for ruta, txt in archivos.items():
    assert "SEGUR_FIN" not in txt
    partes.append(f"cat > {ruta} <<'SEGUR_FIN'\n{txt}\nSEGUR_FIN\n")
partes.append("chmod +x /opt/poc/correr.sh /opt/poc/pruebas/generar_archivos.sh\n"
              "curl -sSL https://github.com/grafana/k6/releases/download/v0.54.0/k6-v0.54.0-linux-amd64.tar.gz | tar xz -C /tmp\n"
              "install /tmp/k6-v0.54.0-linux-amd64/k6 /usr/local/bin/k6\n"
              "/opt/poc/pruebas/generar_archivos.sh /opt/poc/datos\n"
              "printf 'API_URL=%s\\nAPI_KEY=%s\\n' \"")
user_data = {"Fn::Join": ["", ["".join(partes), {"Ref": "ApiUrl"}, "\" \"", {"Ref": "ApiKeyValue"},
             "\" > /opt/poc/env\nchmod 600 /opt/poc/env\n"
             "# apagado automático a las 4 horas para no dejar costos encendidos\n"
             "shutdown -h +240 || true\n"
             "echo LISTO > /opt/poc/estado\n"]]}
tamano = len("".join(partes)) + 200
assert tamano < 16000, tamano

carga = {
  "AWSTemplateFormatVersion": "2010-09-09",
  "Description": "SegurAlpes PoC - generador de carga k6 en la misma region de la pila principal. Acceso solo por Session Manager.",
  "Parameters": {
    "ApiUrl": {"Type": "String", "Description": "Salida ApiUrl de la pila principal"},
    "ApiKeyValue": {"Type": "String", "NoEcho": True, "MinLength": 20},
    "TipoInstancia": {"Type": "String", "Default": "c6i.large"},
    "Ami": {"Type": "AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>",
            "Default": "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"}},
  "Resources": {
    "Rol": {"Type": "AWS::IAM::Role", "Properties": {
      "AssumeRolePolicyDocument": {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}]},
      "ManagedPolicyArns": ["arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"]}},
    "Perfil": {"Type": "AWS::IAM::InstanceProfile", "Properties": {"Roles": [{"Ref": "Rol"}]}},
    # Red propia: no depende de que la cuenta tenga VPC por defecto
    "Vpc": {"Type": "AWS::EC2::VPC", "Properties": {"CidrBlock": "10.50.0.0/16", "EnableDnsSupport": True,
            "EnableDnsHostnames": True, "Tags": [{"Key": "Name", "Value": "segur-alpes-poc-carga"}]}},
    "PuertaInternet": {"Type": "AWS::EC2::InternetGateway"},
    "UnionPuerta": {"Type": "AWS::EC2::VPCGatewayAttachment",
                    "Properties": {"VpcId": {"Ref": "Vpc"}, "InternetGatewayId": {"Ref": "PuertaInternet"}}},
    "Subred": {"Type": "AWS::EC2::Subnet", "Properties": {"VpcId": {"Ref": "Vpc"}, "CidrBlock": "10.50.1.0/24",
               "MapPublicIpOnLaunch": True, "AvailabilityZone": {"Fn::Select": [0, {"Fn::GetAZs": ""}]}}},
    "TablaRutas": {"Type": "AWS::EC2::RouteTable", "Properties": {"VpcId": {"Ref": "Vpc"}}},
    "RutaInternet": {"Type": "AWS::EC2::Route", "DependsOn": "UnionPuerta",
                     "Properties": {"RouteTableId": {"Ref": "TablaRutas"}, "DestinationCidrBlock": "0.0.0.0/0",
                                    "GatewayId": {"Ref": "PuertaInternet"}}},
    "AsociacionRutas": {"Type": "AWS::EC2::SubnetRouteTableAssociation",
                        "Properties": {"SubnetId": {"Ref": "Subred"}, "RouteTableId": {"Ref": "TablaRutas"}}},
    "GrupoSeguridad": {"Type": "AWS::EC2::SecurityGroup", "Properties": {
      "GroupDescription": "Generador de carga: sin entrada, solo salida", "VpcId": {"Ref": "Vpc"},
      "SecurityGroupEgress": [{"IpProtocol": "-1", "CidrIp": "0.0.0.0/0"}]}},
    "Generador": {"Type": "AWS::EC2::Instance", "DependsOn": ["RutaInternet", "AsociacionRutas"], "Properties": {
      "ImageId": {"Ref": "Ami"}, "InstanceType": {"Ref": "TipoInstancia"}, "SubnetId": {"Ref": "Subred"},
      "IamInstanceProfile": {"Ref": "Perfil"}, "SecurityGroupIds": [{"Fn::GetAtt": ["GrupoSeguridad", "GroupId"]}],
      "InstanceInitiatedShutdownBehavior": "stop",
      "Tags": [{"Key": "Name", "Value": "segur-alpes-poc-carga"}],
      "UserData": {"Fn::Base64": user_data}}}},
  "Outputs": {"Instancia": {"Value": {"Ref": "Generador"}}}}
(R / "dist/2-generador-carga.json").write_text(json.dumps(carga, indent=1, ensure_ascii=False))
print("ok; user data ~", tamano, "bytes")
