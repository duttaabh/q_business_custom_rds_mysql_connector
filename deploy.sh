#!/bin/bash

# Q Business Aurora MySQL Connector Deployment Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check CDK
    if ! command -v cdk &> /dev/null; then
        print_error "AWS CDK is not installed. Please install it first: npm install -g aws-cdk@2.99.1"
        exit 1
    fi
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed. Please install it first."
        exit 1
    fi
    
    print_success "All prerequisites are installed"
}

# Setup Python virtual environment
setup_python_env() {
    print_status "Setting up Python virtual environment..."
    
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
    fi
    
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r cdk/requirements.txt
    
    print_success "Python environment setup complete"
}

# Bootstrap CDK (if needed)
bootstrap_cdk() {
    print_status "Checking CDK bootstrap status..."
    
    # Get AWS account and region
    AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
    AWS_REGION=$(aws configure get region)
    
    if [ -z "$AWS_REGION" ]; then
        AWS_REGION="us-east-1"
        print_warning "No default region found, using us-east-1"
    fi
    
    print_status "Using AWS Account: $AWS_ACCOUNT, Region: $AWS_REGION"
    
    # Check if bootstrap is needed
    if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region $AWS_REGION &> /dev/null; then
        print_status "Bootstrapping CDK..."
        cdk bootstrap aws://$AWS_ACCOUNT/$AWS_REGION
        print_success "CDK bootstrap complete"
    else
        print_status "CDK already bootstrapped"
    fi
}

# Prepare Lambda dependencies
prepare_lambda_deps() {
    print_status "Installing Lambda dependencies..."
    
    # Install pymysql directly in lambda directory
    pip install pymysql==1.1.0 -t lambda/ --upgrade
    
    print_success "Lambda dependencies installed"
}

# Deploy the stack
deploy_stack() {
    print_status "Deploying Q Business Aurora MySQL Connector stack..."
    
    # Activate virtual environment
    source .venv/bin/activate
    
    # Prepare Lambda dependencies
    prepare_lambda_deps
    
    # Set environment variable to silence Node.js version warning
    export JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1
    
    # Deploy with CDK
    cdk deploy QBusinessAuroraMySQLConnector --require-approval never
    
    print_success "Stack deployment complete"
}

# Get stack outputs
get_outputs() {
    print_status "Retrieving stack outputs..."
    
    aws cloudformation describe-stacks \
        --stack-name QBusinessAuroraMySQLConnector \
        --query 'Stacks[0].Outputs' \
        --output table
    
    print_success "Stack outputs retrieved"
}

# Main deployment function
main() {
    print_status "Starting Q Business Aurora MySQL Connector deployment..."
    
    check_prerequisites
    setup_python_env
    bootstrap_cdk
    deploy_stack
    get_outputs
    
    print_success "Deployment completed successfully!"
    print_status "Next steps:"
    echo "1. Verify your database credentials in AWS Secrets Manager"
    echo "2. Test the connector using the manual trigger function"
    echo "3. Check CloudWatch logs for sync results"
}

# Run main function
main "$@"