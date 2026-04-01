#!/bin/bash
# 星图 Docker 部署脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印函数
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查 Docker 是否安装
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose 未安装，请先安装 Docker Compose"
        exit 1
    fi

    print_info "Docker 环境检查通过"
}

# 检查环境变量文件
check_env() {
    if [ ! -f .env ]; then
        print_warn ".env 文件不存在，从 .env.example 创建"
        cp .env.example .env
        print_warn "请编辑 .env 文件，填入必要的配置（如 OPENAI_API_KEY）"
        read -p "是否现在编辑 .env 文件？(y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            ${EDITOR:-vi} .env
        else
            print_error "请手动编辑 .env 文件后重新运行此脚本"
            exit 1
        fi
    fi

    # 检查必要的环境变量
    source .env

    if [ "$XINGTU_EMBEDDING_PROVIDER" == "openai" ] && [ -z "$OPENAI_API_KEY" ]; then
        print_error "使用 OpenAI 时必须设置 OPENAI_API_KEY"
        exit 1
    fi

    print_info "环境变量检查通过"
}

# 创建数据目录
create_data_dir() {
    DATA_DIR="${XINGTU_DATA_PATH:-./data}"

    if [ ! -d "$DATA_DIR" ]; then
        print_info "创建数据目录: $DATA_DIR"
        mkdir -p "$DATA_DIR"
    fi

    print_info "数据目录: $DATA_DIR"
}

# 构建镜像
build_image() {
    print_info "开始构建 Docker 镜像..."
    docker-compose build
    print_info "镜像构建完成"
}

# 启动服务
start_services() {
    print_info "启动星图服务..."

    # 检查是否启用 Ollama
    if [ "$XINGTU_EMBEDDING_PROVIDER" == "ollama" ]; then
        print_info "检测到使用 Ollama，同时启动 Ollama 服务"
        docker-compose --profile ollama up -d
    else
        docker-compose up -d
    fi

    print_info "服务启动完成"
}

# 检查服务状态
check_status() {
    print_info "检查服务状态..."
    docker-compose ps

    print_info "检查健康状态..."
    sleep 5

    if docker-compose ps | grep -q "healthy"; then
        print_info "服务运行正常"
    else
        print_warn "服务可能未完全启动，请稍后检查"
    fi
}

# 查看日志
view_logs() {
    print_info "查看服务日志（Ctrl+C 退出）..."
    docker-compose logs -f xingtu-mcp
}

# 停止服务
stop_services() {
    print_info "停止星图服务..."
    docker-compose down
    print_info "服务已停止"
}

# 重启服务
restart_services() {
    print_info "重启星图服务..."
    docker-compose restart
    print_info "服务已重启"
}

# 清理数据
clean_data() {
    read -p "确认要清理所有数据吗？此操作不可恢复！(yes/no) " -r
    echo
    if [[ $REPLY == "yes" ]]; then
        print_warn "清理数据..."
        docker-compose down -v
        rm -rf "${XINGTU_DATA_PATH:-./data}"
        print_info "数据已清理"
    else
        print_info "取消清理操作"
    fi
}

# 显示帮助
show_help() {
    cat << EOF
星图 Docker 部署脚本

用法: $0 [命令]

命令:
    deploy      完整部署（检查环境、构建、启动）
    build       仅构建镜像
    start       启动服务
    stop        停止服务
    restart     重启服务
    status      查看服务状态
    logs        查看服务日志
    clean       清理所有数据（危险操作）
    help        显示此帮助信息

示例:
    $0 deploy       # 首次部署
    $0 logs         # 查看日志
    $0 restart      # 重启服务

EOF
}

# 完整部署流程
deploy() {
    print_info "开始星图 Docker 部署"
    echo "================================"

    check_docker
    check_env
    create_data_dir
    build_image
    start_services
    check_status

    echo "================================"
    print_info "部署完成！"
    echo ""
    print_info "使用以下命令管理服务:"
    echo "  查看日志: $0 logs"
    echo "  停止服务: $0 stop"
    echo "  重启服务: $0 restart"
    echo ""
    print_info "MCP 服务已启动，可以在 Claude Desktop 中配置使用"
}

# 主函数
main() {
    case "${1:-help}" in
        deploy)
            deploy
            ;;
        build)
            check_docker
            build_image
            ;;
        start)
            check_docker
            check_env
            create_data_dir
            start_services
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        status)
            check_status
            ;;
        logs)
            view_logs
            ;;
        clean)
            clean_data
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
