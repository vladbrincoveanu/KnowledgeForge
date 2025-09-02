#!/bin/bash
# KnowledgeForge E2E Test Runner
# Automated script to run end-to-end tests with proper setup and validation

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
TEST_TIMEOUT=300
NEO4J_HOST="localhost"
NEO4J_PORT="7687"
LMSTUDIO_HOST="localhost"  
LMSTUDIO_PORT="1234"
TEST_DATABASE="test_knowledge_forge"

echo -e "${BLUE}🧪 KnowledgeForge E2E Test Runner${NC}"
echo "=================================="

# Function to check if a service is running
check_service() {
    local service_name=$1
    local host=$2
    local port=$3
    
    echo -n "Checking $service_name ($host:$port)... "
    
    if timeout 5 bash -c "cat < /dev/null > /dev/tcp/$host/$port" 2>/dev/null; then
        echo -e "${GREEN}✓ Running${NC}"
        return 0
    else
        echo -e "${RED}✗ Not available${NC}"
        return 1
    fi
}

# Function to setup test environment
setup_test_env() {
    echo -e "\n${YELLOW}🔧 Setting up test environment...${NC}"
    
    # Set test environment variables
    export KF_ENVIRONMENT="test"
    export KF_NEO4J__DATABASE="$TEST_DATABASE"
    export KF_METADATA_STORAGE__HOST="localhost"
    export KF_METADATA_STORAGE__PORT="5432"
    export KF_METADATA_STORAGE__DATABASE="knowledgeforge_test"
    export KF_METADATA_STORAGE__USER="knowledgeforge"
    export KF_METADATA_STORAGE__PASSWORD="knowledgeforge123"
    export KF_EXTRACTION__CONFIDENCE_THRESHOLD="0.5"
    export KF_EXTRACTION__BATCH_SIZE="100"
    export KF_EXTRACTION__SAMPLE_SIZE="100"
    
    echo "✓ Environment variables configured"
    
    # Install/update dependencies
    if [[ ! -f "requirements.txt" ]]; then
        echo -e "${RED}✗ requirements.txt not found${NC}"
        exit 1
    fi
    
    echo "Installing test dependencies..."
    pip install -r requirements.txt --quiet
    echo "✓ Dependencies installed"
}

# Function to validate prerequisites  
check_prerequisites() {
    echo -e "\n${YELLOW}🔍 Checking prerequisites...${NC}"
    
    local all_good=true
    
    # Check Python
    if command -v python3 &> /dev/null; then
        echo "✓ Python 3 available"
    else
        echo -e "${RED}✗ Python 3 not found${NC}"
        all_good=false
    fi
    
    # Check pytest
    if python3 -c "import pytest" 2>/dev/null; then
        echo "✓ pytest available"
    else
        echo -e "${RED}✗ pytest not available${NC}"
        all_good=false
    fi
    
    # Check services
    if ! check_service "Neo4j" "$NEO4J_HOST" "$NEO4J_PORT"; then
        echo -e "${YELLOW}  ℹ️  Start Neo4j: docker run -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:5.15${NC}"
        all_good=false
    fi
    
    if ! check_service "LM Studio" "$LMSTUDIO_HOST" "$LMSTUDIO_PORT"; then
        echo -e "${YELLOW}  ℹ️  Start LM Studio and load a model${NC}"
        all_good=false
    fi
    
    if [ "$all_good" = false ]; then
        echo -e "\n${RED}❌ Prerequisites not met. Please address the issues above.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ All prerequisites met${NC}"
}

# Function to run tests
run_tests() {
    echo -e "\n${YELLOW}🚀 Running E2E tests...${NC}"
    
    local test_args=""
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -v|--verbose)
                test_args="$test_args -v"
                shift
                ;;
            -s|--capture-no)
                test_args="$test_args -s"
                shift
                ;;
            --coverage)
                test_args="$test_args --cov=../api --cov-report=html --cov-report=term"
                shift
                ;;
            --fast)
                test_args="$test_args -m 'not slow'"
                shift
                ;;
            --debug)
                test_args="$test_args --log-cli-level=DEBUG -s"
                shift
                ;;
            --pdb)
                test_args="$test_args --pdb"
                shift
                ;;
            --smoke)
                test_args="$test_args -m smoke"
                shift
                ;;
            *)
                test_args="$test_args $1"
                shift
                ;;
        esac
    done
    
    # Default test arguments
    if [[ -z "$test_args" ]]; then
        test_args="-v --tb=short"
    fi
    
    echo "Running: pytest $test_args"
    echo "Timeout: ${TEST_TIMEOUT}s"
    echo ""
    
    # Run the tests
    if timeout $TEST_TIMEOUT pytest $test_args; then
        echo -e "\n${GREEN}🎉 All tests passed!${NC}"
        return 0
    else
        echo -e "\n${RED}💥 Tests failed or timed out${NC}"
        return 1
    fi
}

# Function to cleanup
cleanup() {
    echo -e "\n${YELLOW}🧹 Cleaning up...${NC}"
    
    # Remove any temporary files created during tests
    rm -rf .pytest_cache/ __pycache__/ .coverage htmlcov/ 2>/dev/null || true
    
    echo "✓ Cleanup completed"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] [PYTEST_ARGS]"
    echo ""
    echo "Options:"
    echo "  -v, --verbose     Verbose test output"
    echo "  -s, --capture-no  Don't capture stdout (shows print statements)"
    echo "  --coverage        Run with coverage reporting"
    echo "  --fast            Skip slow tests"
    echo "  --debug           Run with debug logging"
    echo "  --pdb             Drop into debugger on failures"
    echo "  --smoke           Run only smoke tests"
    echo "  --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Run all tests"
    echo "  $0 --verbose --coverage               # Verbose with coverage"
    echo "  $0 --fast                            # Skip slow tests"
    echo "  $0 test_csv_upload_pipeline.py       # Run specific test file"
    echo "  $0 -k test_complete_csv               # Run tests matching pattern"
    echo ""
}

# Main execution
main() {
    # Handle help
    if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
        show_usage
        exit 0
    fi
    
    # Change to script directory
    cd "$(dirname "${BASH_SOURCE[0]}")"
    
    # Run the pipeline
    setup_test_env
    check_prerequisites
    
    if run_tests "$@"; then
        cleanup
        echo -e "\n${GREEN}✅ E2E test run completed successfully!${NC}"
        exit 0
    else
        cleanup
        echo -e "\n${RED}❌ E2E test run failed!${NC}"
        exit 1
    fi
}

# Handle Ctrl+C gracefully
trap cleanup EXIT

# Run main function with all arguments
main "$@"
