# Guardar cambios en GitHub

El repositorio es [johanvivancx/ARENACASTELL](https://github.com/johanvivancx/ARENACASTELL). El proyecto se desarrolla de forma individual. Git permite guardar cada avance y volver a una versión anterior si hace falta.

Los comandos se ejecutan desde la carpeta `arena-castell`, en la terminal de Visual Studio Code.

## Revisar y subir un cambio

Primero revisa qué archivos cambiaron:

```powershell
git status
git diff
```

Si todo corresponde al cambio que quieres guardar:

```powershell
git add -A
git diff --cached --stat
git commit -m "Describe el cambio realizado"
git push origin main
```

El mensaje debe decir qué cambió. Por ejemplo: “Corrige los enlaces del inicio” o “Agrega el horario de la escuela”. Si un comando falla, revisa el error antes de ejecutar el siguiente.

## Usar una rama para una mejora

Para separar una mejora de la versión principal, puedes trabajar en una rama:

```powershell
git switch main
git switch -c mejora/perfil
```

Después de editar y revisar los archivos:

```powershell
git add -A
git commit -m "Mejora el formulario del perfil"
git push -u origin mejora/perfil
```

En GitHub puedes abrir un Pull Request, revisar las diferencias e integrar la rama en `main`. Usa un nombre distinto para cada mejora. Antes de cambiar de rama, guarda tus cambios en un commit.

## Datos que no se deben subir

`.gitignore` excluye `.env`, `.venv`, archivos temporales y respaldos. Aun así, revisa lo que vas a guardar: una clave escrita por error en otro archivo podría publicarse.

No pongas contraseñas ni tokens dentro de comandos Git. Si GitHub solicita acceso, completa el inicio de sesión con tu cuenta. Para ver la configuración actual:

```powershell
git remote -v
git log --oneline -5
```

Sube solo la rama en la que estás trabajando. No hace falta usar `git push --all`.
