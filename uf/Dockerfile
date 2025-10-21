FROM splunk/universalforwarder:latest

# Принимаем условия и лицензию
ENV SPLUNK_GENERAL_TERMS="--accept-sgt-current-at-splunk-com" \
    SPLUNK_START_ARGS="--accept-license"

USER root
RUN getent group 4 || groupadd -g 4 adm \
 && usermod -a -G 4 splunk
USER splunk

COPY --chown=splunk:splunk system/local /opt/splunkforwarder/etc/system/local

COPY --chown=splunk:splunk apps/ta_osmetrics /opt/splunkforwarder/etc/apps/ta_osmetrics
COPY --chown=splunk:splunk apps/ta_weblogs /opt/splunkforwarder/etc/apps/ta_weblogs
