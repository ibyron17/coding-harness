---
paths:
  - "**/*.java"
  - "**/build.gradle"
  - "**/build.gradle.kts"
  - "**/pom.xml"
---
# Java Testing

> This file extends [common/testing.md](../common/testing.md) with Java specific content.

## Framework

Use the JUnit generation the existing tests use — JUnit 5 (`org.junit.jupiter.api.Test`, with
`useJUnitPlatform()` in Gradle) or JUnit 4 (`org.junit.Test`). Don't mix generations in one test class
or migrate existing tests as part of a feature. A project with no tests yet: default to JUnit 5 (Spring
Boot 2.2+ `spring-boot-starter-test` ships it; on older Spring Boot, use the JUnit 4 the starter brings). Mock with the Mockito the build already provides
(`spring-boot-starter-test` bundles it); on Spring Boot 3.4+ use `@MockitoBean` instead of the
deprecated `@MockBean`.

## Scope

Prefer the narrowest test that covers the change: a plain unit test with constructor-injected mocks,
then a slice test (`@WebMvcTest`, `@JdbcTest`, `@DataJpaTest`, or `@MybatisTest` when its test starter
is on the classpath), and `@SpringBootTest` only when the wiring itself is under test — a full context
starts every connection (database, broker) the application configures.

## Running

- One class: `./gradlew test --tests 'com.example.OrderServiceTest'`, or
  `./mvnw test -Dtest=OrderServiceTest`.
- Whole suite: `./gradlew test`, or `./mvnw test`.
- Tests that need a real database or broker go through the project's existing integration setup
  (Testcontainers, an embedded database, a test profile) — never a shared environment.
