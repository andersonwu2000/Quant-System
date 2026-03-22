export interface RiskRule {
  name: string;
  enabled: boolean;
}

export interface RiskAlert {
  timestamp: string;
  rule_name: string;
  severity: string;
  metric_value: number;
  threshold: number;
  action_taken: string;
  message: string;
}
