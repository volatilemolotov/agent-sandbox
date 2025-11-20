### Installation

Run the following commands to create a `kind` cluster and install analytics tool:

```bash
cd analytics-tool
bash run-kind-and-tool.sh
kubectl apply -f analytics-svc.yaml
cd ..
```

Now we can deploy jupyter lab to make some data analytics:

```bash
kubectl apply -f jupyterlab.yaml
```

Once it's running, you can port-forward your jupyterlab and access on `http://127.0.0.1:8888` by running this command:

```bash
kubectl port-forward "pod/jupyterlab-sandbox" 8888:8888
```

Now you can follow the welcome.ipynb notebook.

## Cleanup

```bash
cd ../../
make delete-kind
```
