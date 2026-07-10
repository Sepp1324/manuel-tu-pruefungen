# Deploy to k3s

Target:

- Host: `manuel.stoegerer-home.cloud`
- Namespace: `organicsr`
- Image: `registry.stoegerer-home.at/organicsr:<tag>`
- Storage: Longhorn PVC `organicsr-data-local`

## 1. DNS

Create an A record:

```text
manuel.stoegerer-home.cloud -> 76.13.140.223
```

## 2. cert-manager

Run on `srv1801804`:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml
kubectl -n cert-manager rollout status deploy/cert-manager --timeout=180s
kubectl -n cert-manager rollout status deploy/cert-manager-webhook --timeout=180s
kubectl -n cert-manager rollout status deploy/cert-manager-cainjector --timeout=180s

kubectl apply -f k8s/05-cluster-issuer.yaml
```

## 3. Secret

Generate a strong password:

```bash
openssl rand -base64 24
```

Create/update the app secret:

```bash
kubectl create namespace organicsr --dry-run=client -o yaml | kubectl apply -f -

kubectl -n organicsr create secret generic organicsr-secrets \
  --from-literal=admin-user=manuel \
  --from-literal=admin-password='<password>' \
  --dry-run=client -o yaml | kubectl apply -f -
```

## 4. Image

Build and push:

```bash
TAG="$(git rev-parse --short HEAD)"
docker build -t "registry.stoegerer-home.at/organicsr:${TAG}" .
docker push "registry.stoegerer-home.at/organicsr:${TAG}"
```

## 5. Apply

```bash
kubectl apply -k k8s
kubectl -n organicsr set image deployment/organicsr organicsr="registry.stoegerer-home.at/organicsr:${TAG}"
kubectl -n organicsr rollout status deployment/organicsr --timeout=180s
```

## 6. Verify

```bash
kubectl -n organicsr get pods,pvc,ingress,certificate
kubectl -n organicsr describe certificate organicsr-tls
curl -I https://manuel.stoegerer-home.cloud
```
