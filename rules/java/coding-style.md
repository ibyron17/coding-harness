---
paths:
  - "**/*.java"
  - "**/build.gradle"
  - "**/build.gradle.kts"
  - "**/pom.xml"
---
# Java Coding Style

> This file extends [common/coding-style.md](../common/coding-style.md) with Java specific content.

## The Build File Sets the Language Level

Read the project's Java level before writing code — `sourceCompatibility` / `targetCompatibility` /
`java { toolchain { languageVersion } }` in Gradle, `maven.compiler.source` / `maven.compiler.release`
in Maven — and use only what that level compiles. This overrides feature advice from any other rule or
example. On Java 8, for instance: no `var` (10), `List.of`/`Map.of` (9), `List.copyOf` (10),
`Optional.isEmpty()` (11), switch expressions (14), text blocks (15), `record` (16).

The framework version gates APIs the same way: Spring Boot 2.x uses `javax.*` (servlet, validation,
persistence), 3.x uses `jakarta.*`. Don't raise the Java, Spring Boot, or build-tool version as a side
effect of a feature change — that is a decision of its own.

## Follow the Stack Already Chosen

Use what the project already uses instead of introducing an alternative: persistence (MyBatis mapper
XML, JPA, or JdbcTemplate), Lombok or plain accessors, the logging facade and backend, the JSON
library, and the injection style (constructor injection unless the module consistently does otherwise).

## Immutability

`final` fields set through the constructor; return unmodifiable views from public APIs
(`Collections.unmodifiableList` on Java 8, `List.copyOf` on 10+).

## Transactions and SQL

- Spring's `@Transactional` works through a proxy: it does not apply to a call from another method of
  the same class, nor to a private method. By default it rolls back only on unchecked exceptions — set
  `rollbackFor` when a checked exception must roll back. Keep remote calls (HTTP, messaging) out of the
  transaction.
- Bind parameters only: MyBatis `#{}`, never `${}` with request data (`${}` is string substitution);
  JPA/JDBC parameters, never string concatenation. A dynamic identifier (a sort column) comes from a
  fixed whitelist.

## Build Tool

Use the wrapper — `./gradlew`, `./mvnw` — so the build-tool version the project targets is the one
that runs. If the build fails because the JDK or build tool doesn't match (e.g. an old Gradle wrapper
on a newer JDK), report it as an environment problem; don't edit build files or build settings to get past
it (wrapper version, language level, dependency/plugin versions, repository URLs, JVM options, …).
