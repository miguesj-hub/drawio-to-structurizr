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

                # Superficie de API: un punto de entrada por caso de uso.
                signInApi = component "SignIn API" "Recibe los intentos de inicio de sesión" "TODO"
                shoppingCartApi = component "Cart API" "Recibe la gestión del carrito de cursos" "TODO"
                paymentApi = component "Payment API" "Recibe las solicitudes de pago" "TODO"
                registrationApi = component "Registration API" "Recibe las solicitudes de registro" "TODO"
                reportingApi = component "Reporting API" "Recibe las consultas de reportes" "TODO"

                # Componentes de dominio.
                securityService = component "Security Component" "Valida credenciales, tokens y roles" "TODO"
                shoppingCartService = component "Cart Component" "Gestiona el carrito de cursos" "TODO"
                paymentService = component "Payment Component" "Procesa los cobros de matrícula" "TODO"
                registrationService = component "Registration Component" "Registra alumnos en cursos" "TODO"
                reportingService = component "Reporting Component" "Genera los reportes académicos y de pagos" "TODO"
                notificationService = component "Notification Component" "Centraliza el envío de notificaciones" "TODO"

                # Adaptadores hacia sistemas externos.
                paymentGatewayAdapter = component "Payment Gateway Adapter" "Traduce los cobros al contrato de la pasarela" "TODO"
                centralRegistryAdapter = component "Registry Form Adapter" "Traduce el formulario al contrato del registro central" "TODO"
                emailAdapter = component "E-mail Adapter" "Traduce las notificaciones al contrato del servicio de correo" "TODO"
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

        # Personas -> sistema. Modeladas contra el contenedor que realmente atienden.
        student -> eCollege.webApplication "Se registra, paga y solicita documentos"
        professor -> eCollege.webApplication "Define requisitos previos y agrega cursos y sílabos"
        administrator -> eCollege.webApplication "Gestiona y revisa cursos y pagos"
        accountant -> eCollege.webApplication "Audita pagos y gestiona facturación"

        # Web -> API. Structurizr deriva de aquí la relación de contenedor
        # webApplication -> monolithicBackend, así que no se declara por separado.
        eCollege.webApplication -> eCollege.monolithicBackend.signInApi "Inicia sesión"
        eCollege.webApplication -> eCollege.monolithicBackend.shoppingCartApi "Gestiona carrito"
        eCollege.webApplication -> eCollege.monolithicBackend.paymentApi "Envía pago"
        eCollege.webApplication -> eCollege.monolithicBackend.registrationApi "Solicita registro"
        eCollege.webApplication -> eCollege.monolithicBackend.reportingApi "Consulta reporte"

        # API -> dominio.
        eCollege.monolithicBackend.signInApi -> eCollege.monolithicBackend.securityService "Valida credenciales"
        eCollege.monolithicBackend.shoppingCartApi -> eCollege.monolithicBackend.securityService "Valida token"
        eCollege.monolithicBackend.shoppingCartApi -> eCollege.monolithicBackend.shoppingCartService "Usa"
        eCollege.monolithicBackend.paymentApi -> eCollege.monolithicBackend.paymentService "Usa"
        eCollege.monolithicBackend.registrationApi -> eCollege.monolithicBackend.registrationService "Usa"
        eCollege.monolithicBackend.reportingApi -> eCollege.monolithicBackend.securityService "Valida rol"
        eCollege.monolithicBackend.reportingApi -> eCollege.monolithicBackend.reportingService "Usa"

        # Dominio -> notificaciones y adaptadores.
        eCollege.monolithicBackend.paymentService -> eCollege.monolithicBackend.paymentGatewayAdapter "Cobra"
        eCollege.monolithicBackend.paymentService -> eCollege.monolithicBackend.notificationService "Solicita notificación de cobro"
        eCollege.monolithicBackend.registrationService -> eCollege.monolithicBackend.registrationApi "Confirma registro"
        eCollege.monolithicBackend.registrationService -> eCollege.monolithicBackend.centralRegistryAdapter "Solicita envío de formulario de registro"
        eCollege.monolithicBackend.registrationService -> eCollege.monolithicBackend.notificationService "Solicita notificación de registro"
        eCollege.monolithicBackend.reportingService -> eCollege.monolithicBackend.notificationService "Envía reporte"
        eCollege.monolithicBackend.notificationService -> eCollege.monolithicBackend.emailAdapter "Envía notificación vía email"

        # Adaptadores -> sistemas externos.
        eCollege.monolithicBackend.paymentGatewayAdapter -> paymentGateway "Solicita cobro" "HTTPS"
        eCollege.monolithicBackend.centralRegistryAdapter -> centralUniversityRegistry "Envía formulario de registro" "HTTPS"
        eCollege.monolithicBackend.emailAdapter -> emailingSystem "Envía correos"

        # TODO(sin conector): en "Component Diagram.drawio" nada conecta con
        # "Base de datos", así que no se sabe qué componente lee o escribe.
        # La relación se mantiene a nivel de contenedor hasta que se dibuje.
        eCollege.monolithicBackend -> eCollege.platformDatabase "Lee y escribe en" "TODO"

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

        component eCollege.monolithicBackend "Components" "Componentes internos del backend monolítico" {
            include *
            autoLayout lr
            title "Component diagram for eCollege - Monolithic Backend"
        }

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
            element "Component" {
                background #85bbf0
                color #000000
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
