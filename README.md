1. Descarregar docker de la web oficial (Community Edition)
2. Instalar docker
3. Reiniciar ordinador
4. Executar això en cmd: `docker build --tag stardog:latest .`
5. Quan hagi acabat, `docker run -d -p 5820:5820 --name myDB -v resources:/stardog stardog:latest`
6. Comprovar que a http://localhost:5820 teniu accés al menú de Stardog. (admin:admin)
7. OPCIONAL: Inicialitzar la base de dades amb un fitxer rdf, anant a la web, premer Data (barra superior), Add