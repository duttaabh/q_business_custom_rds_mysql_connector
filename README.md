# Q Business Aurora MySQL Custom Connector

A custom connector that synchronizes data from Aurora MySQL databases to Amazon Q Business for intelligent search and query capabilities.

## Prerequisites

Before deploying this connector, ensure you have the following prerequisites in place:

### 1. AWS Account and CLI Setup

- **AWS Account** with appropriate permissions
- **AWS CLI** installed and configured with credentials
- **AWS CDK** installed globally: `npm install -g aws-cdk@2.99.1`
- **Python 3.9+** installed on your system
- **Node.js** (for CDK dependencies)

### 2. Aurora MySQL Database Setup

- **Aurora MySQL cluster** running and accessible
- **Database credentials** stored in AWS Secrets Manager
- **VPC and Security Groups** configured for Lambda access
- **Database tables** with data you want to sync to Q Business

#### Secrets Manager Configuration

Your database secret in AWS Secrets Manager must contain the following JSON structure:

```json
{
  "username": "your_db_username",
  "password": "your_db_password"
}
```

**Note**: Host, port, and database name are configured via environment variables in the Lambda function, not in the secret.

### 3. Q Business Application Setup

**IMPORTANT**: You must create a Q Business application, index, and data source BEFORE deploying this connector.

#### 3.1 Create Q Business Application

```bash
# Create a Q Business application
aws qbusiness create-application \
    --display-name "Aurora MySQL Data Explorer" \
    --description "Search and explore data from Aurora MySQL database"
```

Note the `application-id` from the response.

#### 3.2 Create Q Business Index

```bash
# Create an index within your Q Business application
aws qbusiness create-index \
    --application-id YOUR_APPLICATION_ID \
    --display-name "Aurora MySQL Index" \
    --description "Index for Aurora MySQL database content"
```

Note the `index-id` from the response.

#### 3.3 Create Q Business Data Source

```bash
# Create a custom data source within your index
aws qbusiness create-data-source \
    --application-id YOUR_APPLICATION_ID \
    --index-id YOUR_INDEX_ID \
    --display-name "Aurora MySQL Custom Connector" \
    --description "Custom connector for Aurora MySQL database" \
    --type CUSTOM
```

Note the `data-source-id` from the response.

#### 3.4 How to Get Q Business IDs

You can retrieve your Q Business IDs using these commands:

```bash
# List all Q Business applications
aws qbusiness list-applications

# List indexes for a specific application
aws qbusiness list-indices --application-id YOUR_APPLICATION_ID

# List data sources for a specific index
aws qbusiness list-data-sources \
    --application-id YOUR_APPLICATION_ID \
    --index-id YOUR_INDEX_ID
```

### 4. Network Configuration

- **VPC ID** where your Aurora cluster resides
- **Subnet IDs** (preferably private subnets with NAT Gateway access)
- **Security Group IDs** that allow:
  - Outbound HTTPS (443) for AWS API calls
  - Outbound MySQL (3306) to Aurora cluster
  - Inbound/outbound rules as needed for your VPC configuration

### 5. IAM Permissions

Ensure your AWS credentials have permissions for:

- **Lambda**: Create functions, roles, and policies
- **Q Business**: BatchPutDocument, BatchDeleteDocument, GetDataSource, etc.
- **Secrets Manager**: GetSecretValue, DescribeSecret
- **VPC**: Describe VPCs, subnets, security groups
- **CloudFormation**: Create, update, delete stacks
- **IAM**: Create roles and policies for Lambda execution

### 6. Configuration File Setup

**IMPORTANT**: Before deployment, you must create and configure the `cdk.context.json` file.

1. **Copy the example configuration:**
   ```bash
   cp cdk.context.json.example cdk.context.json
   ```

2. **Update `cdk.context.json` with your specific values:**

   The example file (`cdk.context.json.example`) contains sample configurations with detailed comments. Update the following key sections:

   - **Network Configuration**: Your VPC ID, subnet IDs, and security group IDs
   - **Database Configuration**: Aurora cluster endpoint, database name, and Secrets Manager ARN
   - **Q Business Configuration**: Your application ID, index ID, and data source ID
   - **Table Configuration**: Define which tables and fields to sync

3. **Table Configuration Format:**

   The `tables_config` field is a JSON string containing an array of table configurations:

   ```json
   {
     "name": "your_table_name",
     "title_field": "id",
     "content_fields": ["field1", "field2", "field3"],
     "metadata_fields": ["created_at", "updated_at"],
     "where_clause": "status = 'active'",
     "limit": 1000
   }
   ```

   - `name`: Database table name
   - `title_field`: Field to use as document title (usually primary key)
   - `content_fields`: Fields to include in searchable document body
   - `metadata_fields`: Fields to include as document metadata
   - `where_clause`: Optional SQL WHERE clause to filter records
   - `limit`: Maximum records to sync per table

### 7. Verification Steps

Before deployment, verify your setup:

```bash
# Test AWS CLI access
aws sts get-caller-identity

# Verify Q Business application exists
aws qbusiness get-application --application-id YOUR_APPLICATION_ID

# Test database secret access
aws secretsmanager get-secret-value --secret-id YOUR_SECRET_ARN

# Verify VPC and subnet configuration
aws ec2 describe-vpcs --vpc-ids YOUR_VPC_ID
aws ec2 describe-subnets --subnet-ids YOUR_SUBNET_ID
```

## Quick Start

Once all prerequisites are met:

1. **Clone and configure:**
   ```bash
   git clone <repository-url>
   cd q_business_custom_connector
   ```

2. **Set up configuration:**
   ```bash
   # Copy the example configuration
   cp cdk.context.json.example cdk.context.json
   
   # Edit the configuration file with your values
   nano cdk.context.json  # or use your preferred editor
   ```

3. **Deploy:**
   ```bash
   ./deploy.sh
   ```

4. **Test the deployment:**
   ```bash
   # Manually invoke the connector function (replace with your actual function name from deployment output)
   aws lambda invoke \
       --function-name YOUR_FUNCTION_NAME \
       --payload '{"source": "manual-test"}' \
       response.json
   
   # Check the response
   cat response.json
   ```

5. **Monitor:**
   ```bash
   # Check logs (replace with your actual function name from deployment output)
   aws logs tail /aws/lambda/YOUR_FUNCTION_NAME --follow
   ```

## Important Notes

- **Configuration Required**: You MUST copy `cdk.context.json.example` to `cdk.context.json` and update it with your actual values before deployment. The deployment will fail without proper configuration.

- **Data Source Creation**: The Q Business data source must be created BEFORE deploying the Lambda connector, as the connector needs the data source ID to upload documents.

- **Network Access**: Ensure your Lambda function can reach both your Aurora database and AWS Q Business APIs. This typically requires proper VPC configuration with NAT Gateway or VPC endpoints.

- **Secrets Manager**: The database credentials must be stored in Secrets Manager in the exact JSON format specified above (username and password only).

- **Table Configuration**: The `tables_config` in `cdk.context.json` defines which tables and fields to sync. Customize this based on your database schema. See the example file for detailed configuration options.

## Project Structure

```
q_business_custom_connector/
├── cdk/                              # CDK infrastructure code
│   ├── app.py                        # CDK app entry point
│   ├── qbusiness_connector_stack.py  # Main CDK stack definition
│   └── requirements.txt              # CDK Python dependencies
├── lambda/                           # Lambda function code
│   ├── lambda_function.py            # Main connector logic
│   ├── pymysql/                      # PyMySQL dependency (installed by deploy.sh)
│   └── PyMySQL-1.1.0.dist-info/      # PyMySQL metadata (installed by deploy.sh)
├── cdk.context.json.example          # Example configuration file
├── cdk.context.json                  # Your actual configuration (create from example)
├── cdk.json                          # CDK configuration
├── deploy.sh                         # Deployment script
├── cleanup.sh                        # Cleanup script
└── README.md                         # This file
```

## Monitoring and Troubleshooting

### Check Deployment Status
```bash
# View stack outputs
aws cloudformation describe-stacks \
    --stack-name QBusinessAuroraMySQLConnector \
    --query 'Stacks[0].Outputs' \
    --output table
```

### Monitor Lambda Function
```bash
# View recent logs
aws logs describe-log-streams \
    --log-group-name /aws/lambda/YOUR_FUNCTION_NAME \
    --order-by LastEventTime \
    --descending

# Tail logs in real-time
aws logs tail /aws/lambda/YOUR_FUNCTION_NAME --follow
```

### Test Database Connection
```bash
# Test Secrets Manager access
aws secretsmanager get-secret-value --secret-id YOUR_SECRET_ARN

# Verify Q Business resources
aws qbusiness get-application --application-id YOUR_APPLICATION_ID
aws qbusiness get-index --application-id YOUR_APPLICATION_ID --index-id YOUR_INDEX_ID
aws qbusiness get-data-source --application-id YOUR_APPLICATION_ID --index-id YOUR_INDEX_ID --data-source-id YOUR_DATA_SOURCE_ID
```