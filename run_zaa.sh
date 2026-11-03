#!/bin/bash
GCODE="$1"
STL_DIR="/Users/johnfromel/Desktop/modelsSTL"
PYTHON="/Users/johnfromel/Library/Caches/pypoetry/virtualenvs/gcodezaa-urSMRtnC-py3.11/bin/python"
SCRIPT="/Users/johnfromel/Desktop/GCodeZAA"

cd "$SCRIPT"
"$PYTHON" -m gcodezaa "$GCODE" -m "$STL_DIR" -o "$GCODE"
