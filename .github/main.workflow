workflow "Deploy To GAE" {
  on = "push"
  resolves = [
    "Deploy A",
    "Show Config",
  ]
}

action "Run msgfmt" {
  uses = "whtsky/msgfmt-action@master"
}

action "dev branch only" {
  uses = "actions/bin/filter@b2bea07"
  args = "branch dev"
}

action "GCP Authenticate" {
  uses = "actions/gcloud/auth@1a017b23ef5762d20aeb3972079a7bce2c4a8bfe"
  secrets = ["GCLOUD_AUTH"]
  needs = ["dev branch only"]
}

action "Deploy A" {
  uses = "actions/gcloud/cli@1a017b23ef5762d20aeb3972079a7bce2c4a8bfe"
  needs = ["GCP Authenticate", "tweak_config", "Run msgfmt"]
  args = "app deploy --version=1 *.yaml"
  secrets = ["CLOUDSDK_CORE_PROJECT"]
}

action "Show Config" {
  uses = "actions/gcloud/cli@1a017b23ef5762d20aeb3972079a7bce2c4a8bfe"
  needs = ["GCP Authenticate"]
  args = "config list"
}

action "tweak_config" {
  uses = "docker://python:2.7"
  secrets = ["SRC_EMAIL", "DOMAIN"]
  args = "python tweak_config.py"
}
