logging:
  log_level: INFO
  third_party_log_level: WARNING
governance:
  weighting:
    enabled: false
    action_count_threshold: 3
  authorization:
    enabled: false
    default_deny: true
  retry:
    max_attempts: 3
    initial_backoff_seconds: 0.25
    max_backoff_seconds: 5.0
single_company:
  enabled: true
  company_id: "${company_id}"
  auth_mode: "${auth_mode}"
%{ if external_auth_url != "" ~}
  external_auth_url: "${external_auth_url}"
%{ else ~}
  external_auth_url: null
%{ endif ~}
