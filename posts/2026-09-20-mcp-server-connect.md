---
title: "MCP 서버 설치 후 상태 확인법"
date: 2026-09-20
slug: "mcp-server-connect"
summary: "클로드 코드에 MCP 서버를 붙인 뒤 목록의 세 가지 상태를 읽고, 인증·시간 초과·환경변수 문제를 바로 가르는 설치 흐름입니다."
---

클로드 코드에 MCP 서버를 처음 붙이는 분이라면, 서버가 추가됐다는 메시지 뒤에 무엇을 확인해야 하는지부터 잡는 편이 좋습니다. 같은 명령으로 등록해도 원격 주소를 부르는 서버와 내 컴퓨터에서 프로세스를 실행하는 서버는 준비 방식이 다르고, 프로젝트에서만 쓸지 팀과 공유할지도 처음에 정해야 나중에 설정 파일을 다시 옮기지 않습니다.

처음에는 한 번에 끝난 듯 보입니다. 하지만 목록에서 보이는 상태와 실제로 도구를 쓸 수 있는 상태는 같은 뜻이 아니므로, 추가 명령 다음에 확인 명령과 세션 안의 조치까지 이어서 보아야 설치가 끝납니다. 여기에는 처음 붙일 때 놓치기 쉬운 함정도 있습니다.

## 먼저 결론부터

- MCP 서버 등록은 전송 방식에 맞춰 아래처럼 한 명령 계열로 처리합니다.

```bash
claude mcp add --transport http sentry https://mcp.sentry.dev/mcp
claude mcp add playwright -- npx -y @playwright/mcp@latest
```

- 원격 서버는 HTTP를 쓰고, 로컬 프로세스 서버는 stdio를 쓰며, SSE는 구형 방식이라 권장하지 않습니다.
- 기본 범위는 현재 프로젝트용 local이며, 팀 공유 설정은 project 범위로 등록합니다.

```bash
claude mcp add --scope project --transport http sentry https://mcp.sentry.dev/mcp
```

- 등록 뒤 목록에서 `Connected`면 사용할 준비가 된 상태이고, `Needs authentication`이면 세션에서 인증을 이어가야 합니다.
- 연결 표시는 있어도 도구 목록을 못 받아 올 수 있으니, 시간 초과와 서버 응답을 따로 확인해야 합니다.
- API 키가 필요한 서버는 등록할 때 환경변수로 넘기고, 인증 헤더가 필요하면 헤더 옵션을 함께 넣습니다.

```bash
claude mcp add --env KEY=value --header "Authorization: Bearer TOKEN" --transport http sentry https://mcp.sentry.dev/mcp
```

## 전송 방식부터 고릅니다

원격 MCP 서버는 HTTP 주소로 등록합니다. 서버가 이미 호스팅되어 있고 URL을 받았다면 이 방식을 고르면 됩니다.

```bash
claude mcp add --transport http sentry https://mcp.sentry.dev/mcp
```

로컬에서 실행할 도구는 stdio 방식으로 붙입니다. 클로드 코드가 지정한 명령을 실행하고, 그 프로세스와 표준 입출력으로 통신합니다.

```bash
claude mcp add playwright -- npx -y @playwright/mcp@latest
```

SSE도 전송 방식으로 남아 있습니다. 다만 구형 방식이므로 새 서버를 붙일 때 선택할 이유가 없습니다.

## 설정 범위는 사용 위치를 정합니다

범위 선택은 설치 위치를 정하는 일입니다.

local은 기본값이며 현재 프로젝트에서만 씁니다. 설정은 아래 파일에 저장됩니다.

```text
~/.claude.json
```

project 범위는 프로젝트 루트의 설정 파일에 기록되므로 저장소에 커밋하면 팀원이 같은 서버 설정을 함께 받을 수 있고, user 범위는 프로젝트와 관계없이 모든 프로젝트에서 쓰려는 개인 도구에 맞습니다.

```bash
claude mcp add --scope project --transport http sentry https://mcp.sentry.dev/mcp
```

프로젝트 설정 파일은 최소한 아래 구조를 갖습니다. HTTP 서버는 `type`과 `url`을 두고, stdio 서버는 `command`와 `args`를 둡니다.

```json
{
  "mcpServers": {
    "sentry": {
      "type": "http",
      "url": "https://mcp.sentry.dev/mcp"
    },
    "playwright": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp@latest"]
    }
  }
}
```

실제 파일에서도 이 구조를 확인했습니다.

## 목록의 상태를 먼저 읽습니다

등록 직후에는 목록을 확인합니다.

```bash
claude mcp list
```

이 맥에서 실행했을 때는 열두 개 서버가 상태와 함께 나왔습니다. `Connected`는 연결과 도구 목록 수신이 끝난 상태라서 바로 사용할 수 있고, `Needs authentication`은 서버를 추가했지만 계정 인증이 남은 상태이며, 연결 표시는 있으나 도구 목록을 받지 못한 상태는 서버가 요청에 제때 응답하지 못했는지 따로 살펴야 합니다.

조치도 다릅니다.

| 목록에서 보이는 상태 | 다음 조치 |
|---|---|
| Connected | 세션에서 도구를 사용합니다. |
| Needs authentication | 세션 안에서 해당 서버를 골라 인증합니다. |
| 연결됐지만 도구 목록 없음 | 시간 초과와 서버 응답을 확인합니다. |

직접 확인한 목록에는 로컬 데스크톱 앱에 붙는 서버 하나가 요청 시간 초과로 도구 목록을 받지 못한 경우도 있었습니다. 이름별 설정과 상태를 더 보려면 아래 명령을 씁니다.

```bash
claude mcp get <이름>
```

더 이상 쓰지 않는 서버는 제거할 수 있습니다.

```bash
claude mcp remove <이름>
```

## 인증은 세션 안에서 끝냅니다

OAuth가 필요한 서버는 등록만 해도 목록에 인증 필요 상태로 나타납니다. 이때 세션 안에서 MCP 화면을 열고 해당 서버를 선택하면 브라우저가 열리며, 그곳에서 인증을 마치면 됩니다.

```text
/mcp
```

같은 화면에서 도구 목록도 볼 수 있습니다. 등록 명령이 성공했다는 출력만 보고 멈추지 않아야 하는 이유가 여기 있습니다.

## 연결이 안 될 때는 실행 경로를 나눕니다

HTTP URL이 응답하지 않으면 먼저 헤더 요청으로 상태를 봅니다. 주소 자체가 닿지 않는 문제와 인증 문제를 한꺼번에 추측할 필요가 없습니다.

```bash
curl -I <url>
```

stdio 서버가 뜨지 않으면 등록에 넣었던 실행 명령을 터미널에서 직접 실행합니다. 패키지 실행이나 로컬 프로세스 시작 단계에서 멈추는지 확인할 수 있습니다.

시작 시간이 길면 클로드 코드의 시간 제한을 늘립니다.

```bash
MCP_TIMEOUT=60000 claude
```

목록은 연결됐다고 나오는데 도구가 보이지 않으면 API 키 전달부터 확인합니다. 서버가 요구하는 키를 환경변수로 받는 경우에는 등록 명령에 값을 포함해야 합니다.

```bash
claude mcp add --env KEY=value playwright -- npx -y @playwright/mcp@latest
```

## 마무리

다음에는 자주 쓰는 서버 하나를 local 범위로 붙이고, 목록에서 실제 도구가 보이는 자리까지 확인해 보시면 됩니다. 팀이 함께 쓰는 도구라면 그다음에 project 범위와 `.mcp.json` 커밋 여부를 정하면 설정의 의도가 분명해집니다.

목록에 나타나는 세부 상태와 로컬 데스크톱 앱 서버의 시간 초과 사례는 명령 형식만 적힌 공식 문서에서 바로 알기 어렵습니다. 실제 목록 출력은 등록 성공, 인증 대기, 도구 수신 실패가 서로 다른 다음 행동을 요구한다는 점을 보여 주기 때문에, 설치 절차에 목록 확인을 포함해 두는 편이 안전합니다.
