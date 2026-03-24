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

- Detection2D Module
  - [x] Detection2D panel with image display
  - [x] `Detection2DArray` → `ImageAnnotations` conversion
  - [x] 2D bounding box visualization
  - [x] Configurable object labels and IDs via Foxglove variables
  - [x] Object ID, confidence, and label display

- CLI
  - [x] Install Isaac Sim local assets (`sim add local-assets`, v5.1.0)
  - [x] Isaac Sim commands: `sim init`, `sim run` for simplified setup workflows
  - [ ] Isaac ROS commands: `ros init`, `ros run`, `ros build` for streamlined Docker workflows

- Teleop Module
  - [x] Developed a keyboard control panel to publish `geometry_msgs/Twist` messages for 6-DOF movement.

  </details>

<details>
<summary><b>v0.2.0</b></summary>

- Detection3D Module
  - [ ] Detection3D panel for 3D pose and bounding box visualization
  - [ ] `Detection3DArray` support with configurable labels, IDs, and confidence
  - [ ] Interactive object inspection (pose, distance, metadata) with camera mesh and pose axes rendering
  - [ ] Support visualization for Isaac ROS pose estimation packages (CenterPose, DOPE, FoundationPose)

  > _Remaining v0.2.0 features will be added soon in upcoming sprints_

  </details>

<details>
<summary><b>Future Ideas</b></summary>

- Jetson Stat Module: Create a Foxglove panel to monitor Jetson device statistics
- create-isaac: A starter project template generator for developing Isaac ROS and Isaac Sim applications.
- Implement Joystick support in Teleop Module (`pow: Teleop`) support [Logitech F710 Gamepad](https://www.logitechg.com/th-th/products/gamepads/f710-wireless-gamepad.html) and [PS5 DualSense Wireless Controller](https://www.playstation.com/en-th/accessories/dualsense-wireless-controller/)
  </details>
</details>

## Usage

### Pow CLI

Pow CLI usage can be found in the example repository [pow-orin-starter](https://github.com/isaac-powerpack/pow-orin-starter).

### Isaac Powerpack Foxglove

**Installation**

1. Install the Foxglove Studio desktop app from the [Foxglove Studio download page](https://foxglove.dev/downloads/).

2. Follow the instructions in the **Easy installation** section of this blog post, [extending-px4-support](https://foxglove.dev/blog/extending-px4-support), and choose the `isaac-powerpack` package to install the Isaac Powerpack Foxglove extensions instead of PX4 Converter.

**Foxglove Feature Mapping**

The following table maps standard Robotic tasks to our corresponding Isaac Powerpack Foxglove features:

| Tasks              | Isaac Powerpack Foxglove Panel |
| :----------------- | :----------------------------- |
| Object Detection   | pow: Detection 2D              |
| 6-DOF Twist Teleop | pow: Teleop                    |

## Support Matrix

| Platform          | Version / Validation                                                           |
| :---------------- | :----------------------------------------------------------------------------- |
| Device            | ✅ Jetson AGX Orin 32 GB — Tested <br> ⏳ Jetson Orin Nano 8 GB — Pending Test |
| Isaac ROS Version | `release-3.2`                                                                  |
| Isaac Sim         | `5.1.0`                                                                        |
| OS                | Ubuntu 22.04                                                                   |

<br>
 
> 💡 Notes
> - This project is actively developed and tested with Isaac ROS version `release-3.2` on the NVIDIA Jetson AGX Orin 32GB. 
> - The Jetson Orin Nano 8GB (also known as the Jetson Nano Super Developer Kit) is scheduled for upcoming testing.
> - Pow CLI, Isaac Sim extension is tested on Ubuntu 22.04.

## Contribution

See [Contribution Guide](docs/contributing.md)

## License

[Apache-2.0](LICENSE).
