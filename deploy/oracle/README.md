# BoitIA CPU en instancia propia (opcional)

Utiliza llama.cpp y Qwen2.5-1.5B Q4, no una API neuronal de terceros. Candidato para Oracle Ampere Always Free (2 OCPU, 12 GB de RAM), no certificado. El CPU será más lento que Kaggle. Oracle exige una cuenta elegible, puede recuperar instancias ociosas y la capacidad no está garantizada. No habilitar recursos pagos.

Desde la raíz de este repositorio en la VM del propietario:

```bash
docker build -f deploy/oracle/Dockerfile -t boitia-cpu .
docker volume create boitia-cpu-cache
docker run -d --name boitia-cpu --restart unless-stopped -p 127.0.0.1:8080:8080 -v boitia-cpu-cache:/cache boitia-cpu
```

Publicar únicamente mediante reverse proxy HTTPS a `boitia.agustinwojtyszyn.com` con DNS y certificado gestionados por el propietario. No exponer el puerto interno directamente. No introducir claves en el repositorio. Verificar modelo, HTTPS, latencia, CORS y consulta real antes de publicar la URL. No ejecutar actividades artificiales para impedir que Oracle recupere la instancia.
