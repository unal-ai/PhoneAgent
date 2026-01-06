# Third-Party Licenses

This project incorporates code and concepts from the following open-source projects.

## PhoneAgent (Main Project)

- **License**: AGPL-3.0
- **Copyright**: Copyright (C) 2025 PhoneAgent Contributors
- **Description**: Core codebase of this project.

---

## Open-AutoGLM

- **License**: Apache-2.0
- **Copyright**: Copyright (c) 2024 ZAI Organization
- **Repository**: https://github.com/zai-org/Open-AutoGLM
- **Usage**:
  - Vision mode agent architecture (`phone_agent/agent.py`)
  - Action handling logic (`phone_agent/actions/`)
  - distinct analysis and UI interaction logic

---

## YADB - ADB Enhancement Tool

- **License**: LGPL-3.0
- **Author**: ysbing
- **Repository**: https://github.com/ysbing/YADB
- **Usage**: Invoked as a standalone tool via subprocess.
- **Compatibility**: Compatible (used as a standalone binary).

**Description**:
YADB is an ADB enhancement tool (12KB DEX file) providing features like Chinese keyboard input, forced screenshots, and layout dumping.

**License Note (LGPL-3.0)**:
This project invokes `yadb` as an external process. We do not modify the `yadb` source code. It is distributed as a binary resource.

---

## License Compatibility

### Apache-2.0 and AGPL-3.0

Apache-2.0 is a permissive license and is fully compatible with AGPL-3.0. Code from Apache-2.0 projects can be incorporated into AGPL-3.0 projects, provided that the original copyright notices and license attributes are retained.

### LGPL-3.0 and AGPL-3.0

LGPL-3.0 is compatible with AGPL-3.0 when the LGPL component is used as a dynamically linked library or an independent executable. This project uses `yadb` (LGPL-3.0) as an external tool, which satisfies the compatibility requirements.

---

## Dependencies

The project relies on several Python packages, all of which use compatible licenses:

| Dependency | License |
|------------|---------|
| openai | MIT |
| fastapi | MIT |
| pydantic | MIT |
| Pillow | HPND |
| sqlalchemy | MIT |

---

## Acknowledgements

We acknowledge and thank the following projects for their contributions to the ecosystem:

- **Open-AutoGLM**: For the foundational vision agent architecture.
- **YADB**: For ADB enhancement capabilities.
- **Zhipu AI**: For providing multimodal models.
- **FRP**: For NAT traversal.
- **Scrcpy**: For screen mirroring technology.
- **Vue.js / FastAPI / Element Plus**: For the web stack.
