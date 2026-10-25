# SIT Reporter - Guia de Configuracion

## Prerequisitos
- Python 3.11+
- VS Code
- Cuenta JIRA Cloud con Xray instalado
- Cuenta Microsoft 365 Accenture (para envio de emails)

---

## Paso 1: Instalar dependencias

Abre una terminal en VS Code en la carpeta `sit-reporter`:

```bash
pip install -r requirements.txt
```

---

## Paso 2: Configurar JIRA Cloud (OAuth 2.0)

### 2.1 Crear la App OAuth en Atlassian

1. Ve a: https://developer.atlassian.com/console/myapps/
2. Haz clic en **"Create"** -> **"OAuth 2.0 integration"**
3. Dale un nombre (ej: `SIT Reporter`)
4. En **"Permissions"**:
   - Añade **"Jira API"**
   - Activa los scopes: `read:jira-work`, `read:jira-user`, `offline_access`
5. En **"Authorization"**:
   - Callback URL: `http://localhost:8080/callback`
6. Copia el **Client ID** y **Client Secret**

### 2.2 Configurar Xray API Keys

1. En JIRA, ve a: **Xray** -> **API Keys** (en la barra superior o configuracion de Xray)
2. Crea un nuevo par de claves
3. Copia el **Client ID** y **Client Secret** de Xray

---

## Paso 3: Configurar Microsoft Graph (Azure AD)

> **Opcion A (preferida):** Pide a tu administrador de IT de Accenture que registre la app.
> **Opcion B (self-service si tienes permisos):** Sigue los pasos abajo.

### 3.1 Registrar app en Azure AD

1. Ve a: https://portal.azure.com -> **Azure Active Directory** -> **App registrations**
2. **"New registration"**:
   - Nombre: `SIT Reporter`
   - Tipo de cuenta: **"Accounts in this organizational directory only"** (solo Accenture)
   - Redirect URI: `http://localhost` (Public client/native)
3. En **"Authentication"**:
   - Activa **"Allow public client flows"** = Yes
4. En **"API permissions"**:
   - Add a permission -> Microsoft Graph -> Delegated:
     - `Mail.Send`
     - `User.Read`
   - Haz clic en **"Grant admin consent"** (requiere admin)
5. Copia el **Application (client) ID** y el **Directory (tenant) ID**

---

## Paso 4: Crear el archivo .env

Copia `.env.example` a `.env` y rellena los valores:

```bash
cp .env.example .env
```

Edita `.env`:

```env
# JIRA OAuth
JIRA_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
JIRA_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxx
JIRA_REDIRECT_URI=http://localhost:8080/callback
JIRA_BASE_URL=https://tu-empresa.atlassian.net

# Xray Cloud
XRAY_CLIENT_ID=xxxxxxxxxxxxxxxxxxxx
XRAY_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxx

# Microsoft Graph
AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Email
EMAIL_FROM=j.rodriguez.sanchez@accenture.com
EMAIL_TO_EXECUTIVE=director@accenture.com,manager@accenture.com
EMAIL_TO_TRACKING=team-lead@accenture.com,qa@accenture.com
```

---

## Paso 5: Configurar config.yaml

Edita `config.yaml` con los datos de tu proyecto SIT:

```yaml
jira:
  project_key: "TUPROYECTO"    # Clave de tu proyecto en JIRA
  test_plan_key: "TUPROYECTO-1" # Key del Test Plan de Xray

  streams:                      # Define tus streams (usa nombres de componentes JIRA)
    - name: "Backend"
      jql_filter: "component = Backend"
    - name: "Frontend"
      jql_filter: "component = Frontend"

planning:
  start_date: "2026-09-01"      # Inicio del SIT
  end_date: "2026-10-31"        # Fin planificado del SIT
```

---

## Paso 6: Ejecutar

### Primera vez (autenticacion interactiva):
```bash
python main.py --no-email --preview
```
- Se abrira el navegador para autorizar con tu cuenta Accenture en JIRA
- Los tokens se guardan en `.jira_token.json` y `.graph_token_cache.bin` para futuras ejecuciones

### Uso habitual:
```bash
# Generar y enviar ambos reportes
python main.py

# Solo ejecutivo
python main.py --only-executive

# Solo seguimiento
python main.py --only-tracking

# Solo generar HTML (sin enviar email)
python main.py --no-email

# Ver preview en el navegador
python main.py --preview --no-email
```

### Automatizar con Programador de tareas (Windows):
Para ejecutar automaticamente cada dia:
1. Abre **Programador de tareas** de Windows
2. Crea una tarea nueva:
   - Trigger: Diariamente a las 8:00
   - Accion: `python "C:\ruta\a\sit-reporter\main.py"`
   - Directorio de inicio: `C:\ruta\a\sit-reporter\`

---

## Estructura de archivos generados

```
sit-reporter/
├── output/
│   ├── sit_executive_20260925_0800.html
│   └── sit_tracking_20260925_0800.html
├── .jira_token.json        # Token JIRA (auto-generado, NO compartir)
├── .graph_token_cache.bin  # Cache token Graph (auto-generado)
└── ...
```

---

## Troubleshooting

| Error | Causa | Solucion |
|-------|-------|----------|
| `401 Unauthorized` en JIRA | Token caducado o incorrecto | Borra `.jira_token.json` y vuelve a ejecutar |
| `401` en Xray | Client ID/Secret de Xray incorrectos | Verifica en Xray > API Keys |
| `AADSTS` en Graph | App no registrada o sin permisos | Verifica el registro en Azure AD |
| Sin datos de stream | Los componentes no coinciden | Revisa los nombres en `config.yaml` vs JIRA |
| `ModuleNotFoundError` | Dependencias no instaladas | Ejecuta `pip install -r requirements.txt` |

---

## Seguridad

- **NUNCA** subas `.env`, `.jira_token.json` ni `.graph_token_cache.bin` a un repositorio
- Añade estos archivos a `.gitignore`
- Los tokens de JIRA se renuevan automaticamente con el refresh_token
- Los tokens de Graph se renuevan automaticamente con MSAL
