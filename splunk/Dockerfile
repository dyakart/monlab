FROM splunk/splunk:latest

# Добавляем пользователя splunk в группу logreaders
USER root
RUN groupadd -r -g 1001 logreaders || true
RUN usermod -a -G logreaders splunk
USER splunk

# Кладём inputs.conf и приложение с индексом
# сразу выставляем владельца splunk:splunk
COPY --chown=splunk:splunk system/local /opt/splunk/etc/system/local
COPY --chown=splunk:splunk apps/osmetrics_base /opt/splunk/etc/apps/osmetrics_base
COPY --chown=splunk:splunk apps/weblogs_base /opt/splunk/etc/apps/weblogs_base
