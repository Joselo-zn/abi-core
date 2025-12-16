# 🛠 abi-infra/

**Objetivo:** Levantar la infraestructura que ejecuta ABI (local o en la nube) de forma segura, escalable y modular.

---

## 🌐 Infraestructura como código

- **Terraform** – provisión de red, VMs, servicios cloud
- **Ansible** – instalación de dependencias y configuración de entornos

---

## 🧱 Orquestación y clúster

- **Kubernetes (K3s / GKE / EKS)** – orquestador principal
- **Helm** – despliegue de servicios en K8s
- **Docker Registry / GitHub Container Registry** – almacenamiento de imágenes

---

## 🔒 Seguridad & gobernanza

- **Keycloak** – autenticación (SSO, LDAP, OAuth2)
- **OPA (Open Policy Agent)** – políticas de acceso y gobernanza
- **Sigstore / Wazuh / Loki** – logs inmutables y auditoría
- **Vault / Sealed Secrets** – gestión de secretos

---

## 📊 Monitoreo & observabilidad

- **Prometheus** – recolección de métricas
- **Grafana** – visualización
- **Loki** – logging de contenedores
- *(Opcional: Alertmanager, Jaeger para trazas)*

---

## 🧪 Integración continua / CI/CD

- **GitHub Actions / Gitea / Woodpecker CI** – pipelines
- **Inno Setup / NSIS / Snapcraft** – empaquetado de instaladores


abi-infra/
├── terraform/
│   ├── modules/
│   ├── environments/
│   └── main.tf
├── ansible/
│   ├── playbooks/
│   ├── roles/
│   └── inventory/
├── helm/
│   ├── agents/
│   └── weaviate/
├── k8s/
│   ├── manifests/
│   └── secrets/
├── opa/
│   ├── policies/
│   └── gatekeeper/
├── monitoring/
│   └── prometheus-grafana/
├── LICENSE
└── README.md
