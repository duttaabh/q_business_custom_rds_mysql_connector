from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    BundlingOptions,
    BundlingOutput,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_ec2 as ec2,
    aws_secretsmanager as secretsmanager,
    aws_logs as logs,
    RemovalPolicy
)
from constructs import Construct

class QBusinessConnectorStack(Stack):
    """
    CDK Stack for Q Business Aurora MySQL Connector
    """
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Get configuration from context
        vpc_id = self.node.try_get_context("vpc_id")
        subnet_ids = self.node.try_get_context("subnet_ids") or []
        security_group_ids = self.node.try_get_context("security_group_ids") or []
        
        # Database configuration
        db_secret_arn = self.node.try_get_context("db_secret_arn")
        db_host = self.node.try_get_context("db_host") or ""
        db_port = self.node.try_get_context("db_port") or "3306"
        db_name = self.node.try_get_context("db_name") or ""
        db_username = self.node.try_get_context("db_username") or "admin"
        
        # Q Business configuration
        qbusiness_app_id = self.node.try_get_context("qbusiness_application_id") or ""
        qbusiness_index_id = self.node.try_get_context("qbusiness_index_id") or ""
        qbusiness_data_source_id = self.node.try_get_context("qbusiness_data_source_id") or ""
        
        # Tables configuration
        tables_config = self.node.try_get_context("tables_config") or "[]"
        
        # Create VPC configuration if VPC ID is provided
        vpc_config = None
        
        if vpc_id and vpc_id != "":
            # Get VPC reference
            vpc = ec2.Vpc.from_lookup(self, "VPC", vpc_id=vpc_id)
            
            # Get subnets from provided subnet IDs
            subnets = []
            if subnet_ids:
                for i, subnet_id in enumerate(subnet_ids):
                    subnet = ec2.Subnet.from_subnet_id(self, f"Subnet{i}", subnet_id)
                    subnets.append(subnet)
            
            # Get security groups from provided security group IDs
            security_groups = []
            if security_group_ids:
                for i, sg_id in enumerate(security_group_ids):
                    sg = ec2.SecurityGroup.from_security_group_id(self, f"SG{i}", sg_id)
                    security_groups.append(sg)
            
            # Create VPC configuration using provided subnets and security groups
            if subnets:
                vpc_config = {
                    'vpc': vpc,
                    'subnets': ec2.SubnetSelection(subnets=subnets),
                    'security_groups': security_groups if security_groups else None
                }
        
        # Use existing Secrets Manager secret or create new one
        if db_secret_arn:
            # Use existing secret
            db_secret = secretsmanager.Secret.from_secret_complete_arn(
                self, "ExistingDatabaseSecret",
                secret_complete_arn=db_secret_arn
            )
        else:
            # Create new secret (fallback for development)
            db_secret = secretsmanager.Secret(
                self, "DatabaseSecret",
                description="Aurora MySQL database credentials for Q Business connector",
                generate_secret_string=secretsmanager.SecretStringGenerator(
                    secret_string_template=f'{{"username": "{db_username}", "host": "{db_host}", "port": {db_port}, "database": "{db_name}"}}',
                    generate_string_key="password",
                    exclude_characters=' %+~`#$&*()|[]{}:;<>?!\'/@"\\',
                    password_length=32
                ),
                removal_policy=RemovalPolicy.DESTROY
            )
        
        # Create IAM role for Lambda function
        lambda_role = iam.Role(
            self, "ConnectorLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        
        # Add VPC execution role if needed
        if vpc_config:
            lambda_role.add_managed_policy(
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaVPCAccessExecutionRole")
            )
        
        # Add Q Business permissions
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "qbusiness:BatchPutDocument",
                    "qbusiness:BatchDeleteDocument",
                    "qbusiness:GetDataSource",
                    "qbusiness:UpdateDataSource",
                    "qbusiness:GetApplication",
                    "qbusiness:GetIndex"
                ],
                resources=[
                    f"arn:aws:qbusiness:{self.region}:{self.account}:application/{qbusiness_app_id}",
                    f"arn:aws:qbusiness:{self.region}:{self.account}:application/{qbusiness_app_id}/index/{qbusiness_index_id}",
                    f"arn:aws:qbusiness:{self.region}:{self.account}:application/{qbusiness_app_id}/index/{qbusiness_index_id}/data-source/{qbusiness_data_source_id}"
                ] if qbusiness_app_id else ["*"]
            )
        )
        
        # Add Secrets Manager permissions
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret"
                ],
                resources=[db_secret.secret_arn]
            )
        )
        
        # PyMySQL dependency is installed directly in the lambda directory during deployment
        
        # Create Lambda function with PyMySQL layer
        connector_function = _lambda.Function(
            self, "AuroraMySQLConnector",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="lambda_function.lambda_handler",
            code=_lambda.Code.from_asset("lambda"),
            layers=[],
            role=lambda_role,
            timeout=Duration.minutes(15),
            memory_size=1024,
            environment={
                "SECRET_ARN": db_secret.secret_arn,
                "DB_HOST": db_host,
                "DB_NAME": db_name,
                "DB_PORT": db_port,
                "Q_APPLICATION_ID": qbusiness_app_id,
                "Q_INDEX_ID": qbusiness_index_id,
                "Q_DATA_SOURCE_ID": qbusiness_data_source_id
            },
            vpc=vpc_config['vpc'] if vpc_config else None,
            vpc_subnets=vpc_config['subnets'] if vpc_config else None,
            security_groups=vpc_config['security_groups'] if vpc_config else None,
            allow_public_subnet=True,  # Enable public subnet deployment

            description="Q Business Aurora MySQL Connector Lambda Function"
        )
        
        # Create CloudWatch Log Group with explicit retention (avoids Node.js LogRetention function)
        connector_log_group = logs.LogGroup(
            self, "ConnectorLogGroup",
            log_group_name=f"/aws/lambda/{connector_function.function_name}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # EventBridge scheduling removed as requested
        

        
        # Outputs
        CfnOutput(
            self, "ConnectorFunctionName",
            value=connector_function.function_name,
            description="Name of the Aurora MySQL Q Business Connector Lambda function"
        )
        
        CfnOutput(
            self, "ConnectorFunctionArn",
            value=connector_function.function_arn,
            description="ARN of the Aurora MySQL Q Business Connector Lambda function"
        )
        
        CfnOutput(
            self, "DatabaseSecretArn",
            value=db_secret.secret_arn,
            description="ARN of the database credentials secret in Secrets Manager"
        )
        

        
