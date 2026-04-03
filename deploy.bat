@echo off
chcp 65001 >nul
title Bilge Yolcu Deploy
powershell -ExecutionPolicy Bypass -File "C:\Users\EXCALIBUR\bilge-panel\deploy.ps1"
