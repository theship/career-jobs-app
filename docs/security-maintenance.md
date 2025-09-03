# Security Maintenance Guide

## Overview
This document outlines critical security maintenance tasks, audit procedures, and monitoring requirements for the Career Jobs App. All security measures must be regularly reviewed and updated to maintain defense-in-depth protection.

## 1. Row Level Security (RLS) Audit

### Audit Schedule
- **Frequency**: Monthly
- **Responsible**: Security team or DevOps lead
- **Documentation**: Update audit log in `/docs/security-audits/`

### Audit Checklist

#### Core Tables
- [ ] `app_user` - Verify SELECT/INSERT/UPDATE/DELETE policies
- [ ] `resumes` - Check all CRUD operations respect user_id
- [ ] `scores` - Ensure scoring data isolated per user
- [ ] `jobs` - Verify public read, admin-only write
- [ ] `research_cache` - Check cache isolation policies

#### Helper/Junction Tables
- [ ] `user_skills_vocab` - Verify custom vocabulary isolation
- [ ] `resume_skills` - Check skills data tied to user's resumes
- [ ] `activity_logs` - Ensure logs readable only by owner
- [ ] `user_preferences` - Verify preference privacy
- [ ] `pitch_history` - Check pitch generation isolation

#### Audit Commands
```sql
-- List all tables without RLS
SELECT tablename FROM pg_tables 
WHERE schemaname = 'public' 
AND NOT EXISTS (
    SELECT 1 FROM pg_policies 
    WHERE pg_policies.tablename = pg_tables.tablename
);

-- Review policies for a specific table
SELECT * FROM pg_policies WHERE tablename = 'resumes';

-- Test RLS bypass attempts (run as different users)
SET SESSION AUTHORIZATION 'user_a';
SELECT * FROM resumes; -- Should only see user_a's data
```

### Critical RLS Rules
1. **User Isolation**: Users can only access their own data
2. **Service Role Bypass**: Only service role should bypass RLS
3. **No Public Write**: Prevent unauthorized data creation
4. **Audit Trail**: All policy changes must be logged

## 2. Secrets Management

### Secret Storage Requirements

#### Production Environment
- **Vault Solution**: HashiCorp Vault or AWS Secrets Manager
- **Never Store**: Secrets in code, .env files in production, or container images
- **Access Control**: Principle of least privilege for secret access

#### Current Secrets Inventory
| Secret Name | Type | Rotation Frequency | Last Rotated | Owner |
|------------|------|-------------------|--------------|--------|
| SERVICE_SECRET | API Key | 90 days | [DATE] | Backend Team |
| SUPABASE_SERVICE_ROLE_KEY | Service Key | 180 days | [DATE] | DevOps |
| OPENAI_API_KEY | External API | 90 days | [DATE] | AI Team |
| DATABASE_URL | Connection String | 365 days | [DATE] | DevOps |
| JWT_SECRET | Signing Key | 90 days | [DATE] | Security |
| REDIS_PASSWORD | Cache Auth | 180 days | [DATE] | DevOps |

### Rotation Procedures

#### Automated Rotation (Preferred)
```bash
# Example using HashiCorp Vault
vault write auth/token/create/rotate-policy \
    policies="secret-rotation" \
    ttl=90d \
    max_ttl=180d
```

#### Manual Rotation Steps
1. Generate new secret using cryptographically secure method
2. Update secret in vault
3. Deploy to staging environment
4. Verify functionality
5. Deploy to production with rolling update
6. Monitor for errors
7. Remove old secret after confirmation period (24-48 hours)

### Log Redaction

#### Implementation Requirements
- All secrets must be redacted in logs
- Use structured logging with secret detection
- Regular expression patterns for common secret formats

#### Redaction Patterns
```python
# api/utils/logging.py
import re

REDACTION_PATTERNS = [
    (r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([^"\'\s]+)', r'\1[REDACTED]'),
    (r'(token["\']?\s*[:=]\s*["\']?)([^"\'\s]+)', r'\1[REDACTED]'),
    (r'(password["\']?\s*[:=]\s*["\']?)([^"\'\s]+)', r'\1[REDACTED]'),
    (r'(secret["\']?\s*[:=]\s*["\']?)([^"\'\s]+)', r'\1[REDACTED]'),
    (r'Bearer\s+([^"\'\s]+)', r'Bearer [REDACTED]'),
    (r'([a-zA-Z0-9+/]{40,}={0,2})', r'[POTENTIAL_SECRET_REDACTED]'),
]

def redact_secrets(log_message: str) -> str:
    """Redact potential secrets from log messages"""
    for pattern, replacement in REDACTION_PATTERNS:
        log_message = re.sub(pattern, replacement, log_message, flags=re.IGNORECASE)
    return log_message
```

## 3. Security Monitoring & Alerting

### Structured Security Logging

#### Log Format
```json
{
    "timestamp": "2024-01-01T00:00:00Z",
    "level": "WARNING",
    "category": "security",
    "event_type": "auth_failure",
    "user_id": "uuid",
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0...",
    "details": {
        "reason": "invalid_signature",
        "attempted_action": "resume_upload"
    },
    "request_id": "req_123456",
    "service": "fastapi"
}
```

#### Security Event Categories
- `auth_failure` - Authentication failures
- `signature_mismatch` - HMAC validation failures
- `replay_attempt` - Nonce reuse detected
- `rls_violation` - Row Level Security policy violations
- `rate_limit_exceeded` - Rate limiting triggered
- `invalid_input` - Malicious input detected
- `csrf_attempt` - CSRF token validation failure

### Alert Triggers

#### Critical Alerts (Immediate Response)
| Event | Threshold | Action |
|-------|-----------|---------|
| Multiple signature failures | 5 in 1 minute | Block IP, investigate |
| Replay attack detected | Any occurrence | Log and block request |
| RLS bypass attempt | Any occurrence | Audit logs, review permissions |
| Service secret mismatch | 3 in 5 minutes | Possible breach, rotate secrets |

#### Warning Alerts (Review Within 1 Hour)
| Event | Threshold | Action |
|-------|-----------|---------|
| Rate limit exceeded | 10 users in 5 min | Review limits, possible DDoS |
| Invalid input patterns | 20 in 10 minutes | Update WAF rules |
| Unusual geographic access | New country | Verify with user |
| Failed CSRF validation | 5 in 10 minutes | Check implementation |

#### Informational Alerts (Daily Review)
| Event | Threshold | Action |
|-------|-----------|---------|
| New user registrations | Spike > 200% | Marketing campaign check |
| API usage patterns | Deviation > 50% | Capacity planning |
| Failed login attempts | > 100 per day | Review security posture |

### Monitoring Implementation

#### Using Datadog/New Relic
```python
# api/utils/monitoring.py
import structlog
from datadog import DogStatsd

statsd = DogStatsd(host='localhost', port=8125)
logger = structlog.get_logger()

def log_security_event(event_type: str, details: dict, severity: str = "INFO"):
    """Log structured security event with metrics"""
    
    # Structured log
    logger.bind(
        category="security",
        event_type=event_type,
        severity=severity,
        **details
    ).log(severity.lower(), f"Security event: {event_type}")
    
    # Metric
    statsd.increment(f'security.{event_type}', tags=[f'severity:{severity}'])
    
    # Alert on critical events
    if severity == "CRITICAL":
        send_alert(event_type, details)

def send_alert(event_type: str, details: dict):
    """Send immediate alert for critical security events"""
    # Implement PagerDuty/Slack/Email alerting
    pass
```

#### Alert Response Playbooks

##### Playbook: Signature Validation Failure
1. **Detect**: Multiple HMAC failures from same IP
2. **Contain**: Temporarily block IP at CDN level
3. **Investigate**: 
   - Check if legitimate user
   - Review request patterns
   - Check for credential compromise
4. **Remediate**: 
   - If legitimate: Fix client implementation
   - If malicious: Permanent IP ban, update WAF
5. **Document**: Update incident log

##### Playbook: RLS Violation
1. **Detect**: User attempting to access other user's data
2. **Contain**: Revoke user session immediately
3. **Investigate**:
   - Review user's recent activity
   - Check for privilege escalation
   - Audit RLS policies
4. **Remediate**:
   - Fix any policy gaps
   - Review user permissions
   - Consider account suspension
5. **Document**: Security incident report

## 4. Security Maintenance Schedule

### Daily Tasks
- [ ] Review security alert dashboard
- [ ] Check rate limit statistics
- [ ] Monitor authentication failures
- [ ] Verify backup completion

### Weekly Tasks
- [ ] Review security logs for patterns
- [ ] Update threat intelligence feeds
- [ ] Test alert mechanisms
- [ ] Review user access patterns

### Monthly Tasks
- [ ] RLS policy audit
- [ ] Security dependency updates
- [ ] Penetration testing (automated)
- [ ] Review and update WAF rules
- [ ] Secret rotation check

### Quarterly Tasks
- [ ] Full security audit
- [ ] Manual penetration testing
- [ ] Disaster recovery drill
- [ ] Security training update
- [ ] Compliance review

### Annual Tasks
- [ ] Complete security assessment
- [ ] Third-party security audit
- [ ] Policy and procedure review
- [ ] Security architecture review
- [ ] Incident response plan update

## 5. Compliance Checklist

### Data Protection
- [ ] GDPR compliance for EU users
- [ ] CCPA compliance for California users
- [ ] Data retention policies enforced
- [ ] Right to deletion implemented
- [ ] Data portability available

### Security Standards
- [ ] OWASP Top 10 addressed
- [ ] PCI DSS compliance (if processing payments)
- [ ] SOC 2 Type II controls
- [ ] ISO 27001 alignment

## 6. Incident Response Contact

### Escalation Matrix
| Severity | Contact | Response Time |
|----------|---------|---------------|
| Critical | Security Lead + CTO | 15 minutes |
| High | Security Team | 1 hour |
| Medium | DevOps Team | 4 hours |
| Low | On-call Engineer | 24 hours |

### Key Contacts
- **Security Lead**: [Name] - [Phone] - [Email]
- **CTO**: [Name] - [Phone] - [Email]
- **DevOps Lead**: [Name] - [Phone] - [Email]
- **External Security**: [Vendor] - [24/7 Hotline]

## 7. Security Tools & Resources

### Security Scanning
- **SAST**: Semgrep, Bandit (Python)
- **DAST**: OWASP ZAP, Burp Suite
- **Dependencies**: Snyk, Dependabot
- **Secrets**: GitLeaks, TruffleHog

### Monitoring & Alerting
- **SIEM**: Splunk/ELK Stack
- **APM**: Datadog/New Relic
- **Uptime**: Pingdom/UptimeRobot
- **WAF**: Cloudflare/AWS WAF

### Documentation
- **Security Policies**: `/docs/security-policies/`
- **Incident Reports**: `/docs/incidents/`
- **Audit Logs**: `/docs/security-audits/`
- **Runbooks**: `/docs/runbooks/`

---

**Last Updated**: [DATE]
**Next Review**: [DATE + 30 days]
**Document Owner**: Security Team

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>