"""Pacote de configuração do projeto."""

import pymysql

# O Django espera o driver "MySQLdb" (mysqlclient), que exige compilação no
# Windows. O PyMySQL é escrito só em Python e instala sem dor de cabeça.
# Esta linha faz o PyMySQL "se passar" pelo MySQLdb para o Django.
pymysql.install_as_MySQLdb()
