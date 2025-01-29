FROM python:3.13
# Avoid warnings by switching to noninteractive
ENV DEBIAN_FRONTEND=noninteractive
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID


RUN apt-get update \
    && apt-get -y install --no-install-recommends apt-utils dialog 2>&1 \
    && apt-get -y install git procps lsb-release curl bash-completion

RUN apt-get install -y wireguard iproute2 iptables iputils-ping net-tools openresolv  \
    && echo "wireguard" >> /etc/modules \
    && rm -rf /etc/wireguard \
    && mkdir /config \
    && ln -s /config /etc/wireguard \
    && cd /usr/sbin \
    && for i in ! !-save !-restore; do \
        rm -rf iptables$(echo "${i}" | cut -c2-) && \
        rm -rf ip6tables$(echo "${i}" | cut -c2-) && \
        ln -s iptables-legacy$(echo "${i}" | cut -c2-) iptables$(echo "${i}" | cut -c2-) && \
        ln -s ip6tables-legacy$(echo "${i}" | cut -c2-) ip6tables$(echo "${i}" | cut -c2-); \
      done \
    && sed -i 's|\[\[ $proto == -4 \]\] && cmd sysctl -q net\.ipv4\.conf\.all\.src_valid_mark=1|[[ $proto == -4 ]] \&\& [[ $(sysctl -n net.ipv4.conf.all.src_valid_mark) != 1 ]] \&\& cmd sysctl -q net.ipv4.conf.all.src_valid_mark=1|' /usr/bin/wg-quick
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd -s /bin/bash --uid $USER_UID --gid $USER_GID -m $USERNAME \
    # [Optional] Add sudo support for non-root user
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME
#     #
    # Clean up
    # && apt-get autoremove -y \
    # && apt-get clean -y \
    # && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --upgrade pdm

USER $USERNAME
WORKDIR /workspace

ENV DEBIAN_FRONTEND=
ENV LANGUAGE C.UTF-8
ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8
