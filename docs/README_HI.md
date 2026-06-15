# wtftools

[![CI](https://github.com/wachawo/wtftools/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/wtftools/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/wtftools.svg)](https://pypi.org/project/wtftools/)
[![Downloads](https://img.shields.io/pypi/dm/wtftools.svg)](https://pypi.org/project/wtftools/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/wtftools/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/wtftools.svg)](https://pypi.org/project/wtftools/)

> एक ही कमांड से देखें कि अभी आपके Linux सर्वर पर क्या हो रहा है।

[English](https://github.com/wachawo/wtftools/blob/main/README.md) | [Español](https://github.com/wachawo/wtftools/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/wtftools/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/wtftools/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/wtftools/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/wtftools/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/wtftools/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/wtftools/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/wtftools/blob/main/docs/README_JA.md) | **हिन्दी** | [한국어](https://github.com/wachawo/wtftools/blob/main/docs/README_KR.md)

आप किसी सर्वर में लॉग इन करते हैं और कुछ गड़बड़ महसूस होती है। दस अलग-अलग
कमांड (`htop`, `df -h`, `journalctl`, `systemctl --failed`, …) चलाने के बजाय आप एक ही चलाते हैं:

```
$ wtf
# AUDIT
[ OK ] uptime                  3d 4h 12m
[ OK ] load average            0.42 0.51 0.55 / 8 CPU
[ OK ] memory                  4.1GB / 16.0GB used (25%)
[WARN] disk /var               17.0GB / 20.0GB used (85%)
[ OK ] zombie processes        0 zombies
[FAIL] failed systemd units    1 failed unit(s)
[ OK ] crontab syntax          14 cron line(s), no errors

  Summary: 12 ok · 1 warn · 1 fail · 2 skip
```

हरा ठीक है, पीले पर ध्यान देने की ज़रूरत है, लाल को ठीक करने की ज़रूरत है। बस इतना ही।

## इंस्टॉल करें

```bash
pipx install wtftools          # recommended — works on any modern distro
```

`pipx` नहीं है? इनमें से कोई भी तरीका भी काम करता है:

```bash
pip install wtftools           # classic pip (core, no dependencies)
pip install wtftools[full]     # + psutil for richer process/socket info
sudo dpkg -i wtftools_*.deb    # Debian/Ubuntu package (see Releases)
```

इंस्टॉल के बाद आपके पास `wtf` कमांड होता है। इसे आज़माएँ: `wtf`।

## वे कमांड जिन्हें आप वास्तव में इस्तेमाल करेंगे

```bash
wtf              # full health check — start here
wtf problems     # show ONLY what is wrong (warnings + failures)
wtf explain      # what to do about each problem, step by step
```

फिर एक समय में एक संसाधन के बारे में पूछें, जैसे किसी स्विच पर `show` कमांड:

```bash
wtf disk         # is there space? per-mount usage, inodes, read-only
wtf disk --tree  # WHAT is eating the space (largest directories)
wtf cpu          # load, iowait, top CPU consumers
wtf mem          # RAM/swap, OOM kills, top memory consumers
wtf net          # interfaces, IPs, gateway, DNS, listening ports
wtf io           # disk read/write rates, IO-stuck processes
wtf who          # who is logged in, recent logins, failed auth
```

उदाहरण — डिस्क भर रही है, दोषी को खोजें:

```
$ wtf disk --tree /var
# DISK
  /                [████████████████····]  79%  1.4TB / 1.8TB  ext4
  /var             [█████████████████···]  85%  17.0GB / 20.0GB  ext4

# LARGEST UNDER /var
      15.0GB  /var/lib
       3.1GB  /var/log
       1.8GB  /var/log/app
```

बिना पथ के `wtf disk --tree` अपने आप सबसे भरे हुए माउंट को चुन लेता है।

Linux सीख रहे हैं? किसी भी संसाधन कमांड में `--show-commands` जोड़ें और यह उन
क्लासिक कमांड को भी प्रिंट करता है जिन्हें यह बदलता है, ताकि आप उन्हें खुद चला सकें:

```
$ wtf cpu --show-commands
  ...
  equivalent commands:
    $ uptime
    $ top -bn1 | head
    $ ps aux --sort=-%cpu | head
```

## जब कुछ टूट जाए

```bash
wtf problems -v                 # every problem, with detail
wtf events --since 6            # timeline: reboots, OOM kills, failed units
wtf service nginx               # one service: state, restarts, ports, journal
wtf logs --since '2 hours ago'  # recent ERROR+ journal entries by service
wtf explain                     # actionable advice per finding
wtf explain --llm ollama        # or let a local LLM summarize it
```

## स्क्रिप्ट के लिए आउटपुट: grep, awk, jq

जब आप पाइप करते हैं तो रंग अपने आप गायब हो जाते हैं, इसलिए सामान्य `grep` हमेशा काम करता है।
हर कमांड में मशीन-पठनीय फ़ॉर्मेट भी होते हैं — `plain` (टैब-सेपरेटेड,
कोई हेडर नहीं) और `json`। यह फ़्लैग सबकमांड से पहले भी काम करता है:

```bash
wtf -f json disk                         # same as: wtf disk --format json
wtf disk --format plain                  # tab-separated, no headers
wtf disk --format json | jq .            # full JSON

# mounts above 80%:
wtf disk --format json | jq -r '.mounts[] | select(.percent > 80) | .target'

# failed checks only, names column:
wtf audit --format plain | awk -F'\t' '$1 == "fail" {print $2}'

# top directory eating /var, bytes and path:
wtf disk --tree /var --format plain | awk -F'\t' '$1 == "tree" {print $2, $3; exit}'
```

संसाधन कमांड के JSON पेलोड में `schema_version` होता है, ताकि आपकी
स्क्रिप्ट अपग्रेड के बाद भी चलती रहें।

## दैनिक दिनचर्या और मॉनिटरिंग

सुबह की जाँच के लिए एक ही कमांड — ऑडिट, पिछली बार चलने के बाद क्या बदला,
और इवेंट टाइमलाइन, ऊपर एक-पंक्ति का फ़ैसला के साथ:

```bash
wtf daily                       # audit + diff vs yesterday + events
```

यह हर बार चलने पर एक स्नैपशॉट सहेजता है, इसलिए कल का `wtf daily` अंतर (diff) दिखाएगा।
बिना निगरानी के उपयोग के लिए एक crontab पंक्ति (केवल तब मेल करती है जब कुछ गड़बड़ हो):

```cron
0 8 * * * wtf daily --format json > /var/log/wtf-daily.json 2>&1 || mail -s "wtf $(hostname)" you@example.com < /var/log/wtf-daily.json
```

बुनियादी हिस्से अलग से भी उपलब्ध हैं:

```bash
wtf audit --brief               # one line — perfect for MOTD / SSH banner
wtf audit --save                # save a snapshot
wtf diff                        # what changed since the last snapshot
wtf history                     # list saved snapshots

# cron alerting without any monitoring stack:
wtf audit --alert 'mail -s "wtf $WTF_HOST" you@example.com'
wtf audit --alert-on warn --alert 'curl -X POST $SLACK_WEBHOOK -d @-'
```

एग्ज़िट कोड CI/cron के अनुकूल हैं:

| कोड  | अर्थ                                              |
|------|--------------------------------------------------|
| 0    | सब कुछ ठीक                                        |
| 1    | `--strict` के साथ चेतावनियाँ, या crontab त्रुटियाँ |
| 2    | ऑडिट में `[FAIL]` मिला                            |
| 130  | बाधित (Ctrl-C)                                    |

## सभी सबकमांड

| कमांड               | यह क्या करता है                                              |
|---------------------|-------------------------------------------------------------|
| `wtf` / `wtf audit` | हरा/पीला/लाल चेकलिस्ट: क्या ठीक है और क्या नहीं               |
| `wtf problems`      | केवल WARN+FAIL पंक्तियाँ                                     |
| `wtf daily`         | सुबह की जाँच: ऑडिट + पिछली बार के मुक़ाबले diff + इवेंट        |
| `wtf explain`       | प्रति-जाँच व्यावहारिक सलाह; LLM को भेजने के लिए `--llm`        |
| `wtf disk`          | प्रति-माउंट उपयोग; `--tree` सबसे बड़ी डायरेक्टरी दिखाता है     |
| `wtf cpu`           | लोड, iowait, प्रेशर, शीर्ष CPU उपभोक्ता                       |
| `wtf mem`           | RAM/swap, OOM kills, शीर्ष मेमोरी उपभोक्ता                    |
| `wtf net`           | इंटरफ़ेस, गेटवे, DNS, त्रुटियाँ, सुनने वाले पोर्ट             |
| `wtf io`            | प्रति-डिवाइस IO दरें, प्रेशर, अटकी हुई प्रक्रियाएँ            |
| `wtf who`           | लॉग-इन उपयोगकर्ता, हाल के लॉगिन, असफल प्रमाणीकरण              |
| `wtf info`          | एक-पृष्ठ स्नैपशॉट: ऊपर का सब कुछ एक साथ                       |
| `wtf top`           | केंद्रित प्रक्रिया top: cpu/rss से सॉर्ट, उपयोगकर्ता/नाम फ़िल्टर |
| `wtf ports`         | सुनने वाले सॉकेट उनके स्वामी PID/उपयोगकर्ता/कमांड के साथ      |
| `wtf service NAME`  | एक सेवा का विवरण: स्थिति, रीस्टार्ट, मेमोरी, पोर्ट, journal   |
| `wtf logs`          | सेवा के अनुसार समूहित हाल की ERROR+ journal प्रविष्टियाँ      |
| `wtf events`        | कालक्रमिक टाइमलाइन: रीबूट, OOM, असफल यूनिट, …                 |
| `wtf history`       | सहेजे गए ऑडिट स्नैपशॉट की सूची (`wtf audit --save` बनाने के लिए) |
| `wtf diff`          | वर्तमान स्थिति की तुलना सहेजे गए स्नैपशॉट से करें             |
| `wtf crontab`       | सभी मानक crontab स्थानों + प्रति-उपयोगकर्ता crontab को मान्य करें |
| `wtf doctor`        | स्व-निदान: wtftools वास्तव में किन उपकरणों का उपयोग कर सकता है |
| `wtf config`        | प्रभावी कॉन्फ़िग दिखाएँ / उदाहरण प्रिंट करें                  |

`wtftools`,
[`checkcrontab`](https://github.com/wachawo/checkcrontab) को अपने में समेट लेता है और उसकी जगह लेता है —
वही cron वैलिडेटर अब `wtf crontab` पर रहता है।

## उन्नत ऑडिट विकल्प

```bash
wtf audit -v             # show extra detail (failed units, OOM events)
wtf audit --strict       # exit 1 on warnings (CI-friendly)
wtf audit --check memory --check disks    # run named checks only
wtf audit --list-checks  # show all available check short-names
wtf audit --since 1      # look-back window for OOM/auth/kernel (default 24h)
wtf audit --ignore swap --ignore "disk /mnt/Backup"   # silence checks
wtf audit --format csv > audit.csv        # spreadsheet-friendly
wtf audit --format html -o report.html    # self-contained HTML for tickets
wtf audit --format prometheus             # metrics for node_exporter textfile
```

### अंतर्निहित जाँचें

uptime · system state · load average · CPU iowait · PSI cpu/memory/io ·
TCP retransmits · memory · swap · disk (per mount) · inodes ·
read-only mounts · failed systemd units · enabled-but-down services ·
restart loops · network errors · conntrack · journal disk usage · zombies ·
D-state processes · OOM kills · kernel errors · kernel taint · cert expiry ·
open file descriptors · process count · failed auth · time sync ·
pending updates · reboot required · cron daemon · crontab syntax · docker ·
hw temperatures · disk SMART · DNS · HTTP/TCP probes · fail2ban.

## कॉन्फ़िग

थ्रेशोल्ड और इग्नोर इनमें से किसी भी जगह एक INI फ़ाइल में रहते हैं:

- `/etc/wtftools/config.ini`
- `/etc/wtf/config.ini`
- `~/.config/wtftools/config.ini`

पूरी तरह टिप्पणी-युक्त टेम्पलेट के लिए `wtf config --example` चलाएँ। मुख्य बिंदु:

```ini
[thresholds]
disk_warn = 85
disk_fail = 95
swap_warn = 50
swap_fail = 90

[ignore]
checks = swap, updates
result_names =
    disk /mnt/Backup
```

## संगतता

- Python 3.8+
- Linux (systemd डिस्ट्रिब्यूशन सबसे सुगम रास्ता हैं; जब `systemctl` /
  `journalctl` / `psutil` मौजूद न हों तो उपकरण शालीनता से सीमित होकर चलता है)
- कोर CLI के लिए किसी नेटवर्क एक्सेस की ज़रूरत नहीं
- वैकल्पिक नेटवर्क: `wtf explain --llm claude/openai`, `wtf doctor --check-updates`

## स्रोत से

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
# or test without installing:
python3 wtf.py audit
```

## लाइसेंस

MIT
