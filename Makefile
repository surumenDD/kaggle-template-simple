.PHONY: run new list

EXP_ROOT := experiments
TEMPLATE := $(EXP_ROOT)/exp000_sample
PYTHON := python

# 1. 算術演算(10#)を確実に行うため、bashを指定
SHELL := /bin/bash

# =========================
# 新しい実験を作成する
# =========================
new:
	@if [ -z "$(NAME)" ]; then \
		echo "ERROR: NAMEを指定してください (例: make new NAME=hoge)"; \
		exit 1; \
	fi
	@# ディレクトリがない場合のために作成
	@mkdir -p $(EXP_ROOT)
	@LAST=$$(ls -d $(EXP_ROOT)/exp[0-9][0-9][0-9]_* 2>/dev/null \
		| sed -E 's#.*/exp([0-9]{3})_.*#\1#' \
		| sort -n \
		| tail -1); \
	if [ -z "$$LAST" ]; then \
		NEXT="000"; \
	else \
		NEXT=$$(printf "%03d" $$(( 10#$$LAST + 1 ))); \
	fi; \
	NEW_DIR=$(EXP_ROOT)/exp$${NEXT}_$(NAME); \
	if [ -d "$$NEW_DIR" ]; then \
		echo "ERROR: $$NEW_DIR は既に存在します"; \
		exit 1; \
	fi; \
	echo "create: $$NEW_DIR"; \
	mkdir -p $$NEW_DIR/exp; \
	cp $(TEMPLATE)/run.py $$NEW_DIR/ 2>/dev/null || echo "Warning: run.py not found in template"; \
	cp $(TEMPLATE)/config.yaml $$NEW_DIR/ 2>/dev/null || echo "Warning: config.yaml not found in template"; \
	cp $(TEMPLATE)/exp/000.yaml $$NEW_DIR/exp/000.yaml 2>/dev/null || echo "Warning: 000.yaml not found in template"

# =========================
# 実験を実行する
# =========================
run:
	@if [ -z "$(EXP)" ]; then \
		echo "ERROR: EXPを指定してください (例: make run EXP=13)"; \
		exit 1; \
	fi
	@EXP_DIR=$$(ls -d $(EXP_ROOT)/exp$$(printf "%03d" $(EXP))_* 2>/dev/null); \
	if [ -z "$$EXP_DIR" ]; then \
		echo "ERROR: exp$$(printf "%03d" $(EXP)) が見つかりません"; \
		exit 1; \
	fi; \
	echo "run: $$EXP_DIR/run.py"; \
	cd $$EXP_DIR && $(PYTHON) run.py

# =========================
# 実験一覧を表示
# =========================
list:
	@ls -d $(EXP_ROOT)/exp[0-9][0-9][0-9]_* 2>/dev/null | xargs -n 1 basename || echo "no experiments"