ACR=d3acr1
IMAGE=d3-meld-mpi
TAG=latest
az acr login --name $ACR
docker build -f Dockerfile.mpi -t $ACR.azurecr.io/$IMAGE:$TAG .
docker push $ACR.azurecr.io/$IMAGE:$TAG