workspace "eCollege" "Plataforma de matriculación, pagos y documentos académicos" {

    !identifiers hierarchical

    model {

        student = person "Alumno" "Se matricula en cursos, realiza pagos y solicita documentos"
        professor = person "Profesor" "Define requisitos previos y publica cursos y sílabos"
        administrator = person "Administrador" "Gestiona y revisa cursos y pagos"
        accountant = person "Contador" "Audita pagos y gestiona la facturación"

        eCollege = softwareSystem "eCollege" "Plataforma de matriculación, pagos y documentos académicos" {

            webApplication = container "Web Application" "Interfaz web que usan alumnos, profesores, administradores y contadores" "TODO"

            monolithicBackend = container "Monolithic Backend" "Implementa matriculación, pagos, facturación y reportes" "TODO" {
                tags "Backend"
            }

            platformDatabase = container "Platform Database" "Almacena usuarios, cursos, matrículas y pagos" "PostgreSQL" {
                tags "Database"
            }
        }

        centralUniversityRegistry = softwareSystem "Registro Central" "Sistema central de registro de la universidad" {
            tags "External"
        }

        paymentGateway = softwareSystem "Payment Gateway" "Pasarela de pagos de un tercero" {
            tags "External"
        }

        emailingSystem = softwareSystem "Sistema de Correos" "Servicio externo de envío de correo electrónico" {
            tags "External"
        }

        # Personas -> sistema. Modeladas contra el contenedor que realmente atienden,
        # no contra la caja del sistema, para no duplicar la misma dependencia.
        student -> eCollege.webApplication "Se registra, paga y solicita documentos"
        professor -> eCollege.webApplication "Define requisitos previos y agrega cursos y sílabos"
        administrator -> eCollege.webApplication "Gestiona y revisa cursos y pagos"
        accountant -> eCollege.webApplication "Audita pagos y gestiona facturación"

        # Dependencias internas
        eCollege.webApplication -> eCollege.monolithicBackend "Realiza llamadas de API a" "TODO"
        eCollege.monolithicBackend -> eCollege.platformDatabase "Lee y escribe en" "TODO"

        # Dependencias hacia sistemas externos
        eCollege.monolithicBackend -> centralUniversityRegistry "Registra los usuarios nuevos"
        eCollege.monolithicBackend -> paymentGateway "Envía solicitud de cobro con datos de tarjeta" "HTTPS"
        # inferred: este conector no estaba unido en "Container Diagram.drawio"; los
        # extremos se recuperaron por geometría (0.0 px y 0.7 px). Confirmar dirección.
        eCollege.monolithicBackend -> emailingSystem "Envía correos con reportes y facturas"
        emailingSystem -> student "Envía correos al alumno"
    }

    views {

        systemContext eCollege "SystemContext" "Alcance del sistema y actores con los que interactúa" {
            include *
            autoLayout lr
            title "System Context diagram for eCollege"
        }

        container eCollege "Containers" "Unidades ejecutables de eCollege y sus protocolos" {
            include *
            autoLayout lr
            title "Container diagram for eCollege"
        }

        # Sin vista de componentes: "Component Diagram (1).drawio" está vacío
        # (240 bytes, sin figuras). Cuando se dibuje, agregar aquí:
        #   component eCollege.monolithicBackend "Components" { include *; autoLayout lr }

        styles {
            element "Element" {
                metadata true
                fontSize 22
            }
            element "Person" {
                shape person
                background #08427b
                color #ffffff
            }
            element "Software System" {
                background #1168bd
                color #ffffff
            }
            element "Container" {
                background #438dd5
                color #ffffff
            }
            element "Database" {
                shape cylinder
            }
            element "External" {
                background #999999
                color #ffffff
            }
            relationship "Relationship" {
                thickness 2
                routing orthogonal
                fontSize 20
            }
        }
    }

    configuration {
        scope softwaresystem
    }

}
