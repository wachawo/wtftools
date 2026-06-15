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
[FAIL] failed systemd units    1 failed unit(s)

  Summary: 12 ok · 1 warn · 1 fail · 2 skip
```

हरा ठीक है, पीले पर ध्यान देने की ज़रूरत है, लाल को ठीक करने की ज़रूरत है। `wtftools` एक
**केवल-पठन, बिना-निर्भरता वाला CLI** है (केवल Python standard library; `psutil`
वैकल्पिक) जो ढेर सारी डायग्नोस्टिक कमांड को एक पठनीय उत्तर में बदल देता है —
और जब आप इसे पाइप करते हैं तो एक मशीन-पठनीय उत्तर में।

## यह क्या कर सकता है

- **हेल्थ ऑडिट** — 40+ जाँचें (disk, memory, swap, load, PSI, OOM kills,
  failed units, cert expiry, SMART, temperatures, DNS, …) एक
  हरी / पीली / लाल चेकलिस्ट के रूप में।
- **प्रति-संसाधन व्यू** — एक समय में एक चीज़ के बारे में पूछें, किसी स्विच पर `show` कमांड
  की तरह: `wtf disk`, `wtf cpu`, `wtf mem`, `wtf net`, `wtf docker`, …
- **इंसिडेंट ट्रायाज** — `wtf problems`, `wtf events`, `wtf logs`,
  `wtf services <unit>`, `wtf explain` (वैकल्पिक रूप से किसी local या hosted LLM के ज़रिए)।
- **रुझान और अलर्टिंग** — `wtf daily`, स्नैपशॉट + `wtf diff`, cron अलर्ट —
  किसी मॉनिटरिंग स्टैक की ज़रूरत नहीं।
- **स्क्रिप्ट-योग्य** — हर कमांड में `plain` (tab-separated) और `json` आउटपुट होता है
  जिसमें `schema_version` होता है, grep / awk / jq के लिए।
- **शुरुआती-अनुकूल** — `--show-commands` उन क्लासिक कमांड को प्रिंट करता है जिन्हें हर व्यू
  बदलता है, ताकि आप उन्हें हाथ से सीख सकें।

## इंस्टॉल करें

```bash
pipx install wtftools          # recommended — works on any modern distro
pip install wtftools           # or classic pip (core, no dependencies)
pip install wtftools[full]     # + psutil for richer process/socket info
sudo dpkg -i wtftools_*.deb    # Debian/Ubuntu package (see Releases)
```

इंस्टॉल के बाद आपके पास `wtf` कमांड होता है। अपने shell rc में एक पंक्ति जोड़कर
`<Tab>` completion सक्षम करें:

```bash
echo 'eval "$(wtf completion bash)"' >> ~/.bashrc   # bash
echo 'eval "$(wtf completion zsh)"'  >> ~/.zshrc    # zsh
```

नए हैं? [5-मिनट के quickstart](docs/QUICKSTART.md) से शुरू करें।

## कमांड

फ़्लैग के लिए `wtf <command> --help` चलाएँ। हर कमांड उदाहरणों के साथ अपने
रेफ़रेंस पेज से लिंक करता है।

### हेल्थ और मॉनिटरिंग — [docs/AUDIT.md](docs/AUDIT.md)

| command | यह क्या करता है |
|---------|--------------|
| [`wtf` / `wtf audit`](docs/AUDIT.md#wtf-audit) | क्या ठीक है और क्या नहीं, उसकी हरी/पीली/लाल चेकलिस्ट |
| [`wtf problems`](docs/AUDIT.md#wtf-problems) | केवल WARN+FAIL पंक्तियाँ |
| [`wtf daily`](docs/AUDIT.md#wtf-daily) | सुबह की जाँच: ऑडिट + पिछली बार के मुक़ाबले diff + इवेंट |
| [`wtf explain`](docs/AUDIT.md#wtf-explain) | प्रति-जाँच व्यावहारिक सलाह; LLM को भेजने के लिए `--llm` |
| [`wtf events`](docs/AUDIT.md#wtf-events) | टाइमलाइन: रीबूट, OOM kills, असफल यूनिट, … |
| [`wtf logs`](docs/AUDIT.md#wtf-logs) | सेवा के अनुसार समूहित हाल की ERROR+ journal प्रविष्टियाँ |
| [`wtf services`](docs/AUDIT.md#wtf-services) | एक यूनिट में गहराई से जाएँ: स्थिति, रीस्टार्ट, पोर्ट, journal |
| [`wtf diff`](docs/AUDIT.md#wtf-diff) | वर्तमान स्थिति की तुलना सहेजे गए स्नैपशॉट से करें |
| [`wtf history`](docs/AUDIT.md#wtf-history) | सहेजे गए ऑडिट स्नैपशॉट की सूची बनाएँ |
| [`wtf crontab`](docs/AUDIT.md#wtf-crontab) | सिस्टम + प्रति-उपयोगकर्ता crontab को मान्य करें |
| [`wtf doctor`](docs/AUDIT.md#wtf-doctor) | स्व-निदान: wtf किन उपकरणों/फ़ाइलों का उपयोग कर सकता है |

### संसाधन व्यू — [docs/RESOURCES.md](docs/RESOURCES.md)

| command | यह क्या करता है |
|---------|--------------|
| [`wtf disk [PATH]`](docs/RESOURCES.md#wtf-disk) | माउंट अवलोकन; PATH के साथ, सबसे बड़ी फ़ोल्डर; `--tree` गहराई में जाता है |
| [`wtf cpu`](docs/RESOURCES.md#wtf-cpu) | लोड, iowait, प्रेशर, शीर्ष CPU उपभोक्ता |
| [`wtf mem`](docs/RESOURCES.md#wtf-mem) | RAM/swap, OOM kills, शीर्ष मेमोरी उपभोक्ता |
| [`wtf net`](docs/RESOURCES.md#wtf-net) | इंटरफ़ेस, गेटवे, DNS, त्रुटियाँ, सुनने वाले पोर्ट |
| [`wtf io`](docs/RESOURCES.md#wtf-io) | प्रति-डिवाइस IO दरें, प्रेशर, अटकी हुई प्रक्रियाएँ |
| [`wtf who`](docs/RESOURCES.md#wtf-who) | लॉग-इन उपयोगकर्ता, हाल के लॉगिन, असफल प्रमाणीकरण |
| [`wtf temp`](docs/RESOURCES.md#wtf-temp) | /sys/class/hwmon से हार्डवेयर तापमान |
| [`wtf info`](docs/RESOURCES.md#wtf-info) | एक-पृष्ठ स्नैपशॉट: ऊपर का सब कुछ एक साथ |
| [`wtf top`](docs/RESOURCES.md#wtf-top) | केंद्रित प्रक्रिया top: cpu/rss से सॉर्ट, उपयोगकर्ता/नाम से फ़िल्टर |
| [`wtf ports` / `wtf port N`](docs/RESOURCES.md#wtf-ports) | सुनने वाले सॉकेट; एक पोर्ट में गहराई से जाकर PID, exe, cwd तक |
| [`wtf docker [NAME]`](docs/RESOURCES.md#wtf-docker) | कंटेनर compose dir + image/container/log आकार |

### आउटपुट और कॉन्फ़िगरेशन

| command | यह क्या करता है |
|---------|--------------|
| [`wtf config`](docs/CONFIG.md#wtf-config) | प्रभावी कॉन्फ़िग दिखाएँ / एक टिप्पणी-युक्त उदाहरण प्रिंट करें |
| [`wtf completion`](#install) | bash/zsh `<Tab>`-completion स्क्रिप्ट प्रिंट करें |
| [machine output](docs/OUTPUT.md) | `plain`/`json` फ़ॉर्मेट और एक grep·awk·jq कुकबुक |

`wtftools`,
[`checkcrontab`](https://github.com/wachawo/checkcrontab) को अपने में समेट लेता है और उसकी जगह लेता है —
वही cron वैलिडेटर अब `wtf crontab` पर रहता है।

## दस्तावेज़ीकरण

- [QUICKSTART.md](docs/QUICKSTART.md) — 5-मिनट का ऑनबोर्डिंग और एक चीट शीट
- [AUDIT.md](docs/AUDIT.md) — हेल्थ जाँचें, मॉनिटरिंग, exit कोड, पूरी जाँच सूची
- [RESOURCES.md](docs/RESOURCES.md) — उदाहरणों के साथ प्रति-संसाधन व्यू
- [OUTPUT.md](docs/OUTPUT.md) — `plain`/`json` फ़ॉर्मेट और स्क्रिप्टिंग कुकबुक
- [CONFIG.md](docs/CONFIG.md) — कॉन्फ़िग फ़ाइल, थ्रेशोल्ड, जाँचों को अनदेखा करना

## संगतता

- Python 3.8+
- Linux (systemd डिस्ट्रिब्यूशन सबसे सुगम रास्ता हैं; जब `systemctl` /
  `journalctl` / `psutil` मौजूद न हों तो उपकरण शालीनता से सीमित होकर चलता है)
- कोर CLI के लिए किसी नेटवर्क एक्सेस की ज़रूरत नहीं; वैकल्पिक नेटवर्क केवल
  `wtf explain --llm …` और `wtf doctor --check-updates` के लिए

## स्रोत से

```bash
git clone https://github.com/wachawo/wtftools
cd wtftools
pip install -e .
python3 wtf.py audit       # or run it without installing
```

## लाइसेंस

MIT
