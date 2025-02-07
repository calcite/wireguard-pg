FROM python:3.13-slim
# Avoid warnings by switching to noninteractive
ENV DEBIAN_FRONTEND=noninteractive


RUN apt-get update && apt full-upgrade -y && \
    apt-get -y install --upgrade dialog zsh fonts-powerline sudo vim git procps curl

RUN ln -sf /usr/share/zoneinfo/Europe/Prague /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata

# Install Oh My Zsh and Powerlevel10k theme
RUN curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh | bash -s -- --unattended && \
    git clone --depth=1 https://github.com/romkatv/powerlevel10k.git $ZSH_CUSTOM/themes/powerlevel10k

# Set default shell to zsh for root
RUN chsh -s /bin/zsh root

RUN useradd -m -s /bin/zsh dev && \
    echo "dev ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/dev

# Copy Powerlevel10k configuration file
COPY .p10k.zsh /home/dev/.p10k.zsh
COPY .p10k.zsh /root/.p10k.zsh

RUN apt-get install -y lsb-release  wireguard iproute2 iptables iputils-ping net-tools openresolv  \
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


USER dev
RUN curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh | bash -s -- --unattended && \
    git clone --depth=1 https://github.com/romkatv/powerlevel10k.git /home/dev/.oh-my-zsh/themes/powerlevel10k && \
    echo 'source $HOME/.oh-my-zsh/themes/powerlevel10k/powerlevel10k.zsh-theme' >>~/.zshrc && \
    echo '[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh' >> ~/.zshrc && \
    echo 'export PATH=$PATH:/home/dev/.local/bin' >> ~/.zshrc
WORKDIR /workspace

RUN pip install pdm

# RUN python3 -m pip install --upgrade pdm
# ENV DEBIAN_FRONTEND=
# ENV LANGUAGE C.UTF-8
# ENV LC_ALL C.UTF-8
# ENV LANG C.UTF-8
