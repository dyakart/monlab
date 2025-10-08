FROM splunk/splunk:latest

# Кладём inputs.conf и приложение с индексом
# сразу выставляем владельца splunk:splunk
COPY --chown=splunk:splunk system/local /opt/splunk/etc/system/local
COPY --chown=splunk:splunk apps/osmetrics_base /opt/splunk/etc/apps/osmetrics_base
