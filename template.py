from troposphere import Template, Ref, GetAtt, Sub, StackName, Output, Parameter
from troposphere.apigateway import (
    Deployment,
    RestApi,
    Stage,
    Method,
    Integration,
    Resource,
)
from troposphere.awslambda import Function, Permission, Environment, Code
from troposphere.iam import Role, Policy
from troposphere.logs import LogGroup
from awacs.aws import PolicyDocument, Statement, Allow
from awacs.helpers.trust import get_lambda_assumerole_policy
from awacs import route53
import hashlib
import inspect

import handler
import uuid


def create_template():
    t = Template(Description="Dynamic DNS for ddclient")
    hosted_zone_id = t.add_parameter(Parameter("HostedZoneId", Type="String"))
    http_username = t.add_parameter(Parameter("HttpUsername", Type="String"))
    http_password = t.add_parameter(
        Parameter("HttpPassword", Type="String", NoEcho=True)
    )
    role = t.add_resource(
        Role(
            "Role",
            AssumeRolePolicyDocument=get_lambda_assumerole_policy(),
            Policies=[
                Policy(
                    PolicyName="route53-update",
                    PolicyDocument=PolicyDocument(
                        Statement=[
                            Statement(
                                Effect=Allow,
                                Action=[route53.Action("*")],
                                Resource=["*"],
                            )
                        ]
                    ),
                )
            ],
            ManagedPolicyArns=[
                "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
            ],
        )
    )
    function = t.add_resource(
        Function(
            "Function",
            MemorySize=256,
            Timeout=60,
            Handler="index.handler",
            Runtime="python3.6",
            Code=Code(ZipFile=inspect.getsource(handler)),
            Role=GetAtt(role, "Arn"),
            Environment=Environment(
                Variables={
                    "HOSTED_ZONE_ID": Ref(hosted_zone_id),
                    "DDCLIENT_USERNAME": Ref(http_username),
                    "DDCLIENT_PASSWORD": Ref(http_password),
                }
            ),
        )
    )
    log_group = t.add_resource(
        LogGroup(
            "LogGroup",
            LogGroupName=Sub("/aws/lambda/${FunctionName}", FunctionName=Ref(function)),
            RetentionInDays=30,
        )
    )
    permission = t.add_resource(
        Permission(
            "Permission",
            FunctionName=GetAtt(function, "Arn"),
            Principal="apigateway.amazonaws.com",
            Action="lambda:InvokeFunction",
            SourceArn=Sub(
                "arn:${AWS::Partition}:execute-api:${AWS::Region}:${AWS::AccountId}:*"
            ),
            DependsOn=[log_group],
        )
    )
    rest_api = t.add_resource(RestApi("API", Name=StackName))
    resource = t.add_resource(
        Resource(
            "Resource",
            PathPart="{proxy+}",
            ParentId=GetAtt(rest_api, "RootResourceId"),
            RestApiId=Ref(rest_api),
        )
    )
    method_config = dict(
        RestApiId=Ref(rest_api),
        HttpMethod="GET",
        AuthorizationType="NONE",
        Integration=Integration(
            Type="AWS_PROXY",
            IntegrationHttpMethod="POST",
            Uri=Sub(
                "arn:${AWS::Partition}:apigateway:${AWS::Region}:lambda:"
                "path/2015-03-31/functions/${Function.Arn}/invocations"
            ),
        ),
        DependsOn=[permission],
    )
    root_method = t.add_resource(
        Method("Method", ResourceId=GetAtt(rest_api, "RootResourceId"), **method_config)
    )
    proxy_method = t.add_resource(
        Method("ProxyMethod", ResourceId=Ref(resource), **method_config)
    )
    deployment = t.add_resource(
        Deployment(
            "Deployment" + str(uuid.uuid4()).replace("-", "").upper(),
            RestApiId=Ref(rest_api),
            DependsOn=[root_method, proxy_method],
        )
    )
    stage = t.add_resource(
        Stage(
            "Stage",
            DeploymentId=Ref(deployment),
            RestApiId=Ref(rest_api),
            StageName="nic",
        )
    )

    t.add_output(
        Output("Hostname", Value=Sub("${API}.execute-api.${AWS::Region}.amazonaws.com"))
    )
    t.add_output(
        Output(
            "Url",
            Value=Sub(
                "https://${API}.execute-api.${AWS::Region}.amazonaws.com/${Stage}"
            ),
        )
    )
    return t


if __name__ == "__main__":
    print(create_template().to_json(indent=4))
