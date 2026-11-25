# React Native

- Long or unbounded lists use a virtualised list, never a mapped scroll view. Give stable keys, keep rows light and their props referentially stable.
- Load images at display size, with caching and fixed dimensions.
- Run animations on the UI thread; change transform and opacity, not layout properties.
- Prefer native navigators and native modals over JavaScript re-creations.
- Use pressable components with a large enough touch target and visible pressed feedback.
- Respect safe areas, the keyboard and both platforms' back behaviour.
- All visible strings sit inside text components; a stray value from `&&` can crash a screen.
- Native dependencies belong in the app package so linking finds them.
- Measure performance in a release build on a real low-end device; debug builds mislead.
