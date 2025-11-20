set -e

export KIND_CLUSTER_NAME="agent-sandbox"

# following develop guide to make and deploy agent-sandbox to kind cluster
cd ../../../
make build
make deploy-kind
cd examples/analytics/analytics-tool

echo "Building sandbox-runtime image..."
docker build -t sandbox-runtime .

echo "Loading sandbox-runtime image into kind cluster..."
kind load docker-image sandbox-runtime:latest --name "${KIND_CLUSTER_NAME}"


echo "Applying CRD and deployment..."
kubectl apply -f sandbox-python-kind.yaml
