# Deployment

## Laufender Betrieb
Der GitHub-Actions-Workflow (`.github/workflows/deploy-k3s.yml`) baut das Image,
prueft es per Smoke-Test, wendet die Infrastruktur-Manifeste einzeln an und rollt
das Deployment per `kubectl set image` + `rollout restart` aus (**kein** `apply -k`).
Das App-Secret `organicsr-secrets` wird dabei aus GitHub-Actions-Secrets angelegt
bzw. ein Platzhalter-Passwort migriert. Fuer den normalen Betrieb ist nichts
manuell zu tun – nur das GitHub-Secret `ADMIN_PASSWORD` muss gesetzt sein
(optional `ADMIN_USER`, `NOTIFY_TOKEN`, `ANTHROPIC_API_KEY`).

## Neuen Cluster aufsetzen (einmalig, in dieser Reihenfolge)

1. **cert-manager installieren** (cluster-weit, z. B. per Helm) – Voraussetzung
   für die TLS-Automatik.
2. **DNS** von `chemie.stoegerer-home.cloud` auf die Traefik-LoadBalancer-IP
   zeigen lassen (`kubectl -n kube-system get svc traefik`).
3. **App-Basis anlegen** (Namespace, Storage, Ingress, CronJob):

   ```bash
   kubectl apply -k k8s
   ```

   `k8s/kustomization.yaml` enthaelt das Secret **bewusst nicht** (nur Platzhalter).
   Das App-Secret separat mit einem **starken** Passwort erzeugen:

   ```bash
   kubectl -n organicsr create secret generic organicsr-secrets \
     --from-literal=admin-user=manuel \
     --from-literal=admin-password="$(openssl rand -base64 18)"
   ```

   Alternativ das GitHub-Secret `ADMIN_PASSWORD` setzen und den Deploy-Workflow
   laufen lassen – der legt `organicsr-secrets` selbst an.
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
