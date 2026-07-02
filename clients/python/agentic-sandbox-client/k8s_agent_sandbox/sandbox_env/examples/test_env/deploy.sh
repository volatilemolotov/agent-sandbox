#!/bin/bash

gcloud builds submit .
sleep 2
kubectl delete -f warmpool.yaml
kubectl delete -f template.yaml
sleep 3
kubectl apply -f template.yaml
sleep 1
kubectl apply -f warmpool.yaml
