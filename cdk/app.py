#!/usr/bin/env python3
import os
from aws_cdk import App, Environment
from qbusiness_connector_stack import QBusinessConnectorStack

app = App()

# Get environment configuration
env = Environment(
    account=app.node.try_get_context("account") or os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=app.node.try_get_context("region") or os.environ.get("CDK_DEFAULT_REGION")
)

# Deploy the stack
QBusinessConnectorStack(
    app, "QBusinessAuroraMySQLConnector",
    env=env,
    description="Q Business Aurora MySQL Connector"
)

app.synth()