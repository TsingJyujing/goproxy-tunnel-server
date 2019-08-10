FROM python:3.7
RUN pip3 install django
RUN mkdir /app
WORKDIR /app
ENV EXPOSE_PORT 8080
CMD python manage.py runserver --noreload 0.0.0.0:$EXPOSE_PORT
COPY . .