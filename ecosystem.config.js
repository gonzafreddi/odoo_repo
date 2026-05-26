module.exports = {
  apps: [
    {
      name: "odoo",
      script: "./odoo-bin",
      interpreter: "python3",
      args: [
        "-c",
        "/home/suplex/odoo_suplex/etc/odoo19.conf"
      ],
      cwd: "/home/suplex/odoo_suplex/odoo_repo",
      autorestart: true,
      watch: false,
    },
  ],
};
