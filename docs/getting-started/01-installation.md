# Instalación

Bienvenido a ABI-Core. En esta guía aprenderás a instalar todo lo necesario para comenzar a construir sistemas de agentes de IA.

## Requisitos

Antes de comenzar, asegúrate de tener:

- **Python 3.11 o superior**
- **Docker y Docker Compose** (para ejecutar agentes y servicios)
- **4GB de RAM mínimo** (8GB recomendado)
- **10GB de espacio en disco** (para modelos de IA)

## Paso 1: Instalar Python

### En Linux/macOS

Python 3.11+ generalmente ya está instalado. Verifica tu versión:

```bash
python3 --version
```

Si necesitas instalarlo:

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3-pip

# macOS (con Homebrew)
brew install python@3.11
```

### En Windows

Descarga Python desde [python.org](https://www.python.org/downloads/) y sigue el instalador.

**Importante**: Marca la opción "Add Python to PATH" durante la instalación.

## Paso 2: Instalar Docker

Docker es esencial para ejecutar agentes y servicios en contenedores.

### En Linux

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Agregar tu usuario al grupo docker
sudo usermod -aG docker $USER

# Reiniciar sesión para aplicar cambios
```

### En macOS/Windows

Descarga e instala [Docker Desktop](https://www.docker.com/products/docker-desktop/)

### Verificar Instalación

```bash
docker --version
docker-compose --version
```

Deberías ver algo como:
```
Docker version 24.0.0
Docker Compose version v2.20.0
```

## Paso 3: Instalar ABI-Core

### Instalación desde PyPI (Recomendado)

La forma más fácil es instalar desde PyPI:

```bash
pip install abi-core-ai
```

### Instalación desde Código Fuente

Para desarrollo o para obtener las últimas características:

```bash
# Clonar el repositorio
git clone https://github.com/Joselo-zn/abi-core.git
cd abi-core

# Instalar en modo desarrollo
pip install -e .
```

## Paso 4: Verificar Instalación

Verifica que ABI-Core se instaló correctamente:

```bash
abi-core --version
```

Deberías ver:
```
abi-core version 0.1.0b105
```

Verifica los comandos disponibles:

```bash
abi-core --help
```

Deberías ver:
```
Usage: abi-core [OPTIONS] COMMAND [ARGS]...

  ABI-Core CLI - Build AI agent systems

Commands:
  create            Create new projects and components
  add               Add components to existing project
  remove            Remove components from project
  provision-models  Download and configure LLM models
  run               Start the project services
  status            Check project and services status
  info              Show project information
```

## Solución de Problemas

### Error: "command not found: abi-core"

**Causa**: Python no está en tu PATH o pip instaló en un directorio no incluido.

**Solución**:

```bash
# Encuentra dónde se instaló
pip show abi-core-ai

# Agrega el directorio bin a tu PATH
export PATH="$HOME/.local/bin:$PATH"

# Para hacerlo permanente, agrégalo a ~/.bashrc o ~/.zshrc
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Error: "Permission denied" al ejecutar Docker

**Causa**: Tu usuario no tiene permisos para ejecutar Docker.

**Solución**:

```bash
# Linux: Agregar usuario al grupo docker
sudo usermod -aG docker $USER

# Reiniciar sesión
logout
# Volver a iniciar sesión
```

### Error: "Python version too old"

**Causa**: Tienes Python 3.10 o anterior.

**Solución**: Instala Python 3.11 o superior siguiendo las instrucciones del Paso 1.

## Próximos Pasos

¡Felicidades! Ya tienes ABI-Core instalado. Ahora puedes:

1. [Entender qué es ABI-Core](02-what-is-abi.md)
2. [Aprender conceptos básicos](03-basic-concepts.md)
3. [Crear tu primer proyecto](04-first-project.md)

## Recursos Adicionales

- [Documentación de Docker](https://docs.docker.com/)
- [Documentación de Python](https://docs.python.org/3/)
- [Repositorio de ABI-Core](https://github.com/Joselo-zn/abi-core)

---

**¿Necesitas ayuda?** Abre un issue en [GitHub](https://github.com/Joselo-zn/abi-core/issues) o escribe a jl.mrtz@gmail.com
