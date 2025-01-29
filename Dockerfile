FROM python:3.13-slim
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update \
    && apt-get -y install --no-install-recommends \
        curl procps wireguard iproute2 iptables iputils-ping net-tools openresolv \
    # Setup wireguard
    && echo "wireguard" >> /etc/modules \
    && rm -rf /etc/wireguard \
    && mkdir /config \
    && ln -s /config /etc/wireguard \
    # && cd /usr/sbin \
    # && for i in ! !-save !-restore; do \
    #     rm -rf iptables$(echo "${i}" | cut -c2-) && \
    #     rm -rf ip6tables$(echo "${i}" | cut -c2-) && \
    #     ln -s iptables-legacy$(echo "${i}" | cut -c2-) iptables$(echo "${i}" | cut -c2-) && \
    #     ln -s ip6tables-legacy$(echo "${i}" | cut -c2-) ip6tables$(echo "${i}" | cut -c2-); \
    #     done \
    && sed -i 's|\[\[ $proto == -4 \]\] && cmd sysctl -q net\.ipv4\.conf\.all\.src_valid_mark=1|[[ $proto == -4 ]] \&\& [[ $(sysctl -n net.ipv4.conf.all.src_valid_mark) != 1 ]] \&\& cmd sysctl -q net.ipv4.conf.all.src_valid_mark=1|' /usr/bin/wg-quick \
    # Clean up
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

COPY src/ /app
COPY pyproject.toml /app/
COPY pdm.lock  /app/
RUN python -m pip install --upgrade --no-cache-dir py.lockfile2 \
  && mkdir -p /wheels \
  && py.lockfile -s /app/pdm.lock -t /wheels \
  && pip install /wheels/* \
  && rm -rf /wheels

# USER wireguard
ENV DEBIAN_FRONTEND=
ENV LANGUAGE C.UTF-8
ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]