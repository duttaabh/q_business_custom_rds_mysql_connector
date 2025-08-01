#!/bin/bash

# Q Business Aurora MySQL Connector Cleanup Script

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

# Confirm deletion
confirm_deletion() {
    print_warning "This will delete the Q Business Aurora MySQL Connector stack and all associated resources."
    print_warning "This action cannot be undone!"
    echo ""
    print_status "Resources that will be deleted:"
    echo "- Lambda functions (connector and manual trigger)"
    echo "- EventBridge rule for scheduled sync"
    echo "- IAM roles and policies"
    echo "- CloudWatch log groups"
    echo "- Secrets Manager secret (if created by this stack)"
    echo ""
    
    read -p "Are you sure you want to proceed? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        print_status "Cleanup cancelled."
        exit 0
    fi
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
        print_error "AWS CDK is not installed. Please install it first."
        exit 1
    fi
    
    # Check if stack exists
    if ! aws cloudformation describe-stacks --stack-name QBusinessAuroraMySQLConnector &> /dev/null; then
        print_warning "Stack 'QBusinessAuroraMySQLConnector' does not exist or has already been deleted."
        exit 0
    fi
    
    print_success "Prerequisites check complete"
}

# Setup Python virtual environment
setup_python_env() {
    print_status "Setting up Python virtual environment..."
    
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
    fi
    
    source .venv/bin/activate
    pip install --upgrade pip > /dev/null 2>&1
    pip install -r cdk/requirements.txt > /dev/null 2>&1
    
    print_success "Python environment setup complete"
}

# Get stack information before deletion
get_stack_info() {
    print_status "Retrieving stack information..."
    
    # Get stack outputs
    aws cloudformation describe-stacks \
        --stack-name QBusinessAuroraMySQLConnector \
        --query 'Stacks[0].Outputs' \
        --output table
    
    print_success "Stack information retrieved"
}

# Delete the CDK stack
delete_stack() {
    print_status "Deleting Q Business Aurora MySQL Connector stack..."
    
    # Activate virtual environment
    source .venv/bin/activate
    
    # Set environment variable to silence Node.js version warning
    export JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1
    
    # Delete the stack
    cdk destroy QBusinessAuroraMySQLConnector --force
    
    print_success "Stack deletion complete"
}

# Clean up local files
cleanup_local() {
    print_status "Cleaning up local files..."
    
    # Remove CDK output files
    rm -rf cdk.out
    
    # Remove Python cache
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    
    # Remove response files
    rm -f response.json
    
    # Clean up Lambda dependencies
    rm -rf lambda/pymysql* lambda/PyMySQL* 2>/dev/null || true
    find lambda/ -name "*.dist-info" -type d -exec rm -rf {} + 2>/dev/null || true
    
    print_success "Local cleanup complete"
}

# Verify deletion
verify_deletion() {
    print_status "Verifying stack deletion..."
    
    # Wait a moment for AWS to update
    sleep 5
    
    if aws cloudformation describe-stacks --stack-name QBusinessAuroraMySQLConnector &> /dev/null; then
        print_warning "Stack still exists. It may take a few more minutes to complete deletion."
        print_status "You can check the status with:"
        echo "aws cloudformation describe-stacks --stack-name QBusinessAuroraMySQLConnector"
    else
        print_success "Stack has been successfully deleted"
    fi
}

# Main cleanup function
main() {
    print_status "Starting Q Business Aurora MySQL Connector cleanup..."
    echo ""
    
    check_prerequisites
    confirm_deletion
    echo ""
    
    get_stack_info
    echo ""
    
    setup_python_env
    delete_stack
    cleanup_local
    verify_deletion
    
    echo ""
    print_success "Cleanup completed successfully!"
    echo ""
    print_status "Note: The following may still exist and require manual cleanup if needed:"
    echo "- Your existing Aurora MySQL database and Secrets Manager secret"
    echo "- Your Q Business application, index, and data source"
    echo "- Any VPC, subnets, or security groups that were referenced but not created by this stack"
    echo "- CloudWatch logs (will be automatically deleted based on retention policy)"
}

# Run main function
main "$@"