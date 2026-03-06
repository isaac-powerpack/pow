<p align="center">
    <img src="https://raw.githubusercontent.com/bemunin/isaac-powerpack/main/docs/public/logo.svg" width="400"/>
</p>

> [!IMPORTANT] 
> **Scope Change for v0.1.0**
> In the next version, starting with v0.1.0, this repository focuses exclusively on Isaac Sim project management (`pow-cli`). `pow-foxglove` has been migrated to a standalone repository. Planned Isaac ROS commands have been removed from the roadmap in favor of a new `pow ros` command for Isaac Sim Ros workspace Docker container access.

Key features include:

- 🛠️ CLI tools — to streamline Isaac ROS and Isaac Sim project setup and management

🚧 This project is in early development. Features and APIs are still evolving and subject to breaking changes.

🙋 We’ll open this project for contributions soon.

[Read the Docs to Learn More](docs/index.md)

## Features & Milestones

<details open>
<summary><b>v0.1.0 (🏃 In Progress)</b></summary>

- CLI
  - [x] Install Isaac Sim local assets (`sim add local-assets`, v5.1.0)
  - [x] Isaac Sim commands: `sim init`, `sim run` for simplified setup workflows

  </details>

<details>
<summary><b>Future Ideas</b></summary>

- create-isaac: A starter project template generator for developing Isaac Sim applications.
  </details>
</details>

### Pow CLI

Pow CLI usage can be found in the example repository [pow-orin-starter](https://github.com/isaac-powerpack/pow-orin-starter).

| Platform          | Version / Validation |
| :---------------- | :------------------- |
| Isaac Sim         | `5.1.0`              |
| OS                | Ubuntu 22.04         |

<br>

> 💡 Notes
> - Pow CLI, Isaac Sim extension is tested on Ubuntu 22.04.

## Contribution

See [Contribution Guide](docs/contributing.md)

## License

[Apache-2.0](LICENSE).
