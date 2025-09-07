# Infrastructure Composition 

> **Note**: The concepts and definitions in this section are based on "Infrastructure as Code, Third Edition" by Kief Morris (O'Reilly Media, 2024).

An infrastructure composition is a collection of IaaS resources organized around a workload-relevant concern _[1]_. Infrastructure compositions are typically used to define the integration of multiple infrastructure stacks. The compositions may define configuration values for the stacks, and integration points between stacks that have dependencies on one another_[1]_.

The contents of an infrastructure composition and the way it is presented for configuration and use should make sense to its users, who are usually the teams responsible for configuring, deploying, and managing the applications and services that use the infrastructure. In contrast, infrastructure stacks are grouped around technical concerns, especially how IaaS resources should be grouped for provisioning_[1]_.


## Stack
 Is a collection of IaaS resources defined, created, and modified as an independent, complete unit._[1]_

## Code library

Infrastructure resources grouped by how their code is shared and reused across stacks. _[1]_

## IaaS resource

The smallest unit of infrastructure that can be independently defined and provisioned.
## References

_[1]_: Morris, Kief. *Infrastructure as Code: Dynamic Systems for the Cloud Age*, 3rd ed. O'Reilly Media, 2024.

