FROM splunk/universalforwarder:latest

# Принимаем условия и лицензию, задаём пароль UF
ENV SPLUNK_GENERAL_TERMS="--accept-sgt-current-at-splunk-com" \
    SPLUNK_START_ARGS="--accept-license"

USER root
RUN getent group 4 || groupadd -g 4 adm \
 && usermod -a -G 4 splunk
USER splunk

COPY --chown=splunk:splunk system/local /opt/splunkforwarder/etc/system/local

COPY --chown=splunk:splunk apps/ta_webmetrics /opt/splunkforwarder/etc/apps/ta_webmetrics
COPY --chown=splunk:splunk apps/ta_weblogs /opt/splunkforwarder/etc/apps/ta_weblogs

