FROM splunk/universalforwarder:latest

# Принимаем условия и лицензию, задаём пароль UF
ENV SPLUNK_GENERAL_TERMS="--accept-sgt-current-at-splunk-com" \
    SPLUNK_START_ARGS="--accept-license" \
    SPLUNK_PASSWORD="Uf!Pass123"

COPY --chown=splunk:splunk apps/ta_osmetrics /opt/splunkforwarder/etc/apps/ta_osmetrics
COPY --chown=splunk:splunk apps/ta_weblogs /opt/splunkforwarder/etc/apps/ta_weblogs
COPY --chown=splunk:splunk system/local /opt/splunkforwarder/etc/system/local
