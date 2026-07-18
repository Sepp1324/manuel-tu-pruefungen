# Deployment

## Laufender Betrieb
Der GitHub-Actions-Workflow (`.github/workflows/deploy-k3s.yml`) baut das Image,
prueft es per Smoke-Test und rollt es via `kubectl apply -k k8s` aus. Für den
normalen Betrieb ist nichts manuell zu tun.

## Neuen Cluster aufsetzen (einmalig, in dieser Reihenfolge)

1. **cert-manager installieren** (cluster-weit, z. B. per Helm) – Voraussetzung
   für die TLS-Automatik.
2. **DNS** von `chemie.stoegerer-home.cloud` auf die Traefik-LoadBalancer-IP
   zeigen lassen (`kubectl -n kube-system get svc traefik`).
3. **App-Basis anlegen** (u. a. Namespace + Secret):

   ```bash
   kubectl apply -k k8s
   ```

   Vorher `k8s/15-secret.yaml` mit echten Werten füllen (Admin-Passwort etc.).
4. **TLS-Bootstrap anwenden** (ClusterIssuer + Certificate → Secret `organicsr-tls`):

   ```bash
   # Zuerst die ACME-E-Mail in k8s/bootstrap/05-cluster-issuer.yaml setzen!
   kubectl apply -k k8s/bootstrap
   ```

   cert-manager stellt das Zertifikat über eine HTTP-01-Challenge (Port 80 via
   Traefik) aus und erneuert es automatisch. Der Ingress
   (`k8s/30-ingress.yaml`) terminiert TLS damit selbst.

Danach ist der Cluster vollständig eingerichtet – kein manuelles Erstellen von
Zertifikaten oder Secrets mehr nötig.

## Warum ist der TLS-Bootstrap getrennt?
`ClusterIssuer` ist cluster-weit und einmalig. Der Deploy-Workflow läuft
`apply -k k8s` bei **jedem** Push; ein Issuer dort mitlaufen zu lassen, würde
riskieren, die laufende Zertifikatserneuerung bei jedem Deploy anzufassen.
Deshalb liegt er in `k8s/bootstrap/` und wird pro Cluster genau einmal angewandt.
