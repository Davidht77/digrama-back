# Diagram Generation Serverless API

This project implements a serverless API for generating various types of diagrams (flowcharts, ERDs, JSON schemas) using AWS Lambda and API Gateway, managed with the Serverless Framework. The diagram generation logic is implemented in Python, leveraging the `diagrams` library.

## Project Structure

- `serverless.yml`: Defines the serverless service, AWS resources (Lambda functions, API Gateway endpoints, DynamoDB table, S3 bucket), and plugins.
- `package.json`: Manages project dependencies (primarily for Serverless Framework CLI and plugins).
- `requirements.txt`: Lists Python dependencies for the Lambda functions.
- `src/functions/generate_flowchart.py`: Contains the Lambda function logic for generating diagrams from Python source code, acting as the `generateFlowchart` endpoint.
- `src/functions/generate_erd.py`: Contains the Lambda function logic for generating diagrams from Python source code, acting as the `generateERD` endpoint.
- `src/functions/generate_json_schema.py`: Contains the Lambda function logic for generating diagrams from Python source code, acting as the `generateJSONSchema` endpoint.

## Setup and Deployment

### Prerequisites

- **Python 3.9+** and `pip` for dependency management.
- **AWS CLI** configured with appropriate credentials.
- **Serverless Framework CLI** installed globally (`npm install -g serverless`).
- **Graphviz** installed on your system (required by the `diagrams` library for rendering).

### Installation

1.  **Install Python dependencies**:

    ```bash
    pip install -r requirements.txt
    ```

2.  **Install Serverless Framework plugins**:

    ```bash
    serverless plugin install -n serverless-python-requirements
    ```

### Local Development

To run the API locally using `serverless-offline`:

```bash
serverless offline start
```

This will start a local server, typically at `http://localhost:3000`.

### Deployment to AWS

To deploy the API to your AWS account:

```bash
serverless deploy
```

After deployment, the API Gateway endpoint URL will be displayed in the terminal output.

## API Endpoints

The API provides the following endpoints for generating diagrams. Each endpoint supports `aws`, `gcp`, `azure`, and `onprem` diagram types.

### `POST /generate-flowchart`

Generates a flowchart diagram from Python source code.

**Request Body Example (AWS)**:

```json
{
  "type": "aws",
  "source": "from diagrams import Diagram\nfrom diagrams.aws.compute import EC2\n\nwith Diagram(\"My AWS Diagram\"):\n    EC2(\"Web Server\")"
}
```

**Request Body Example (GCP)**:

```json
{
  "type": "gcp",
  "source": "from diagrams import Diagram\nfrom diagrams.gcp.compute import ComputeEngine\n\nwith Diagram(\"My GCP Diagram\"):\n    ComputeEngine(\"VM Instance\")"
}
```

**Request Body Example (Azure)**:

```json
{
  "type": "azure",
  "source": "from diagrams import Diagram\nfrom diagrams.azure.compute import VirtualMachine\n\nwith Diagram(\"My Azure Diagram\"):\n    VirtualMachine(\"Azure VM\")"
}
```

**Request Body Example (On-Premise)**:

```json
{
  "type": "onprem",
  "source": "from diagrams import Diagram\nfrom diagrams.onprem.compute import Server\n\nwith Diagram(\"My On-Premise Diagram\"):\n    Server(\"Application Server\")"
}
```

### `POST /generate-erd`

Generates an ERD diagram from Python source code.

**Request Body Example (AWS)**:

```json
{
  "type": "aws",
  "source": "from diagrams import Diagram\nfrom diagrams.aws.database import RDS\n\nwith Diagram(\"My AWS ERD\"):\n    RDS(\"Database\")"
}
```

**Request Body Example (ERD)**:

```json
{
  "type": "erd",
  "source": "postgresql://user:password@host:port/database"
}```
```

### `POST /generate-json-schema`

Generates a JSON Schema diagram from Python source code.

**Request Body Example (AWS)**:

```json
{
  "type": "aws",
  "source": "from diagrams import Diagram\nfrom diagrams.aws.network import APIGateway\n\nwith Diagram(\"My AWS JSON Schema\"):\n    APIGateway(\"API Gateway\")"
}
```

## CI/CD with GitHub Actions (Conceptual)

This project can be integrated with GitHub Actions for automated deployment on every push to the `main` branch. A conceptual workflow is outlined below:

```yaml
# .github/workflows/deploy.yml
name: Deploy Serverless API

on: [push]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v3
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          npm install -g serverless # Install Serverless CLI
          serverless plugin install -n serverless-python-requirements
      - name: Deploy to AWS
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: serverless deploy
```

This workflow assumes you have configured `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` as GitHub Secrets in your repository.