FROM caddy:2-alpine

COPY bin/mihomo /usr/local/bin/mihomo

EXPOSE 7890 7891 9090

ENTRYPOINT ["/usr/local/bin/mihomo"]
CMD ["-d", "/root/.config/mihomo"]
