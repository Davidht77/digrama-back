# Dockerfile (Versión Final Final y Robusta)

# 1. Usamos la imagen base oficial de AWS para Python 3.9
FROM public.ecr.aws/lambda/python:3.9

# 2. ¡LA CORRECCIÓN!
#    Instalamos TODAS las dependencias, incluyendo las de RENDERIZADO.
RUN yum install -y \
    gcc \
    gcc-c++ \
    make \
    libtool \
    libpng-devel \
    libjpeg-devel \
    libtiff-devel \
    libwebp-devel \
    git \
    curl \
    expat-devel \
    # LIBRERÍAS PARA RENDERIZAR PNG, SVG, ETC.
    cairo-devel \
    pango-devel

# 3. Descargamos, compilamos e instalamos una versión MODERNA de Graphviz
#    Ahora, el script ./configure encontrará cairo y pango y activará el soporte para PNG.
WORKDIR /tmp
RUN curl -L https://gitlab.com/api/v4/projects/4207231/packages/generic/graphviz-releases/9.0.0/graphviz-9.0.0.tar.gz | tar -xz
WORKDIR /tmp/graphviz-9.0.0
RUN ./configure
RUN make
RUN make install

# 4. Copiamos nuestro archivo de requerimientos de Python
COPY src/requirements.txt ${LAMBDA_TASK_ROOT}/

# 5. Instalamos las dependencias de Python.
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# 6. Copiamos todo el código de nuestra aplicación
COPY src/ ${LAMBDA_TASK_ROOT}/src/

# 7. Limpiamos el directorio temporal
RUN rm -rf /tmp/graphviz-9.0.0

# 8. Establecemos la ruta de búsqueda de librerías
ENV LD_LIBRARY_PATH="/usr/local/lib:${LD_LIBRARY_PATH}"

# 9. Restablecemos el directorio de trabajo
WORKDIR ${LAMBDA_TASK_ROOT}

# 10. Definimos el comando por defecto
CMD [ "src.functions.generate_erd.generate_erd" ]