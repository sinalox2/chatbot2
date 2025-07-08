# Usa una imagen oficial de Python 3
FROM python:3.10-slim

# Directorio de trabajo
WORKDIR /app

# Copia las dependencias e instálalas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código
COPY . .

# Expone el puerto que tu app use (si es 8000, 3000, etc.)
ENV PORT 8000
# Comando de arranque
CMD ["python", "app.py"]