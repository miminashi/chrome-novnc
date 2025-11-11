FROM alpine:3.19.1

LABEL AboutImage="Alpine_Chromium_NoVNC"

LABEL Maintainer="Apurv Vyavahare <apurvvyavahare@gmail.com>"

# VNC Server Title(w/o spaces)
ENV VNC_TITLE="Chromium"

# VNC Resolution(720p is preferable)
ENV VNC_RESOLUTION="1280x720"

# VNC Shared Mode
ENV VNC_SHARED=false

# Local Display Server Port
ENV DISPLAY=:0

ENV PORT=8080
# NoVNC Port
ENV NOVNC_PORT=$PORT

# Heroku No-Sleep Mode
ENV NO_SLEEP=false

# Locale
ENV LANG=ja_JP.UTF-8
ENV LANGUAGE=ja_JP.UTF-8
ENV LC_ALL=ja_JP.UTF-8
ENV TZ="Asia/Tokyo"

COPY assets/ /

RUN	apk update && \
	apk add --no-cache tzdata ca-certificates supervisor curl wget openssl bash python3 py3-requests sed unzip xvfb x11vnc websockify openbox chromium nss alsa-lib font-noto font-noto-cjk && \
# noVNC SSL certificate
	openssl req -new -newkey rsa:4096 -days 36500 -nodes -x509 -subj "/C=IN/O=Dis/CN=www.google.com" -keyout /etc/ssl/novnc.key -out /etc/ssl/novnc.cert > /dev/null 2>&1 && \
# TimeZone
	cp /usr/share/zoneinfo/$TZ /etc/localtime && \
	echo $TZ > /etc/timezone && \
# Wipe Temp Files
	apk del build-base curl wget unzip tzdata openssl && \
	rm -rf /var/cache/apk/* /tmp/*
ENTRYPOINT ["supervisord", "-l", "/var/log/supervisord.log", "-c"]

CMD ["/config/supervisord.conf"]
