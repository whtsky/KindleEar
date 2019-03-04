workflow "Deploy To GAE" {
  on = "push"
  resolves = [
    "Deploy B",
    "Show Config"
  ]
}

action "Run msgfmt" {
  uses = "whtsky/msgfmt-action@master"
}

action "GCP Authenticate" {
  uses = "actions/gcloud/auth@1a017b23ef5762d20aeb3972079a7bce2c4a8bfe"
  secrets = ["GCLOUD_AUTH"]
}

action "Deploy A" {
  uses = "actions/gcloud/cli@1a017b23ef5762d20aeb3972079a7bce2c4a8bfe"
  needs = ["GCP Authenticate", "update SRC_EMAIL", "Run msgfmt"]
  args = "app deploy --version=1 ./app.yaml ./module-worker.yaml"
  secrets = ["CLOUDSDK_CORE_PROJECT"]
}

action "Deploy B" {
  uses = "actions/gcloud/cli@1a017b23ef5762d20aeb3972079a7bce2c4a8bfe"
  needs = ["Deploy A"]
  args = "app deploy --version=1 ."
  secrets = ["CLOUDSDK_CORE_PROJECT"]
}

action "Show Config" {
  uses = "actions/gcloud/cli@1a017b23ef5762d20aeb3972079a7bce2c4a8bfe"
  needs = ["GCP Authenticate"]
  args = "config list"
}

action "update DOMAIN" {
  uses = "actions/bin/sh@master"
  args = "sed -i \"s/^DOMAIN = \\\"http\\(\\|s\\):\\/\\/.*\\.appspot\\.com\\/\\\"/DOMAIN = \\\"http:\\/\\/$CLOUDSDK_CORE_PROJECT\\.appspot\\.com\\/\\\"/g\" ./config.py"
  secrets = ["CLOUDSDK_CORE_PROJECT"]
}

action "update SRC_EMAIL" {
  uses = "actions/bin/sh@master"
  needs = ["update DOMAIN"]
  args = "sed -i \"s/^SRC_EMAIL = \\\".*\\\"/SRC_EMAIL = \\\"$SRC_EMAIL\\\"/g\" ./config.py"
  secrets = ["SRC_EMAIL"]
}
