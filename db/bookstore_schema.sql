--
-- PostgreSQL database dump
--

\restrict bookstore

-- Dumped from database version 16.15 (Debian 16.15-1.pgdg13+2)
-- Dumped by pg_dump version 16.15 (Debian 16.15-1.pgdg13+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: app; Type: SCHEMA; Schema: -; Owner: migrator
--

CREATE SCHEMA app;


ALTER SCHEMA app OWNER TO migrator;

--
-- Name: shop; Type: SCHEMA; Schema: -; Owner: migrator
--

CREATE SCHEMA shop;


ALTER SCHEMA shop OWNER TO migrator;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: authors; Type: TABLE; Schema: shop; Owner: migrator
--

CREATE TABLE shop.authors (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    surname character varying(100) NOT NULL
);


ALTER TABLE shop.authors OWNER TO migrator;

--
-- Name: authors_id_seq; Type: SEQUENCE; Schema: shop; Owner: migrator
--

ALTER TABLE shop.authors ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME shop.authors_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: book_author; Type: TABLE; Schema: shop; Owner: migrator
--

CREATE TABLE shop.book_author (
    book_id integer NOT NULL,
    author_id integer NOT NULL
);


ALTER TABLE shop.book_author OWNER TO migrator;

--
-- Name: books; Type: TABLE; Schema: shop; Owner: migrator
--

CREATE TABLE shop.books (
    id integer NOT NULL,
    title character varying(255) NOT NULL,
    price numeric(12,2) NOT NULL,
    pages integer,
    genre_id integer NOT NULL,
    CONSTRAINT books_pages_check CHECK ((pages > 0)),
    CONSTRAINT books_price_check CHECK ((price >= (0)::numeric))
);


ALTER TABLE shop.books OWNER TO migrator;

--
-- Name: COLUMN books.price; Type: COMMENT; Schema: shop; Owner: migrator
--

COMMENT ON COLUMN shop.books.price IS 'Текущая цена в каталоге';


--
-- Name: books_id_seq; Type: SEQUENCE; Schema: shop; Owner: migrator
--

ALTER TABLE shop.books ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME shop.books_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: genres; Type: TABLE; Schema: shop; Owner: migrator
--

CREATE TABLE shop.genres (
    id integer NOT NULL,
    name character varying(100) NOT NULL
);


ALTER TABLE shop.genres OWNER TO migrator;

--
-- Name: genres_id_seq; Type: SEQUENCE; Schema: shop; Owner: migrator
--

ALTER TABLE shop.genres ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME shop.genres_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: order_item; Type: TABLE; Schema: shop; Owner: migrator
--

CREATE TABLE shop.order_item (
    id integer NOT NULL,
    order_id integer NOT NULL,
    book_id integer NOT NULL,
    unit_price numeric(12,2) NOT NULL,
    quantity integer NOT NULL,
    CONSTRAINT order_item_quantity_check CHECK ((quantity > 0)),
    CONSTRAINT order_item_unit_price_check CHECK ((unit_price >= (0)::numeric))
);


ALTER TABLE shop.order_item OWNER TO migrator;

--
-- Name: COLUMN order_item.unit_price; Type: COMMENT; Schema: shop; Owner: migrator
--

COMMENT ON COLUMN shop.order_item.unit_price IS 'Цена за 1 шт. в момент заказа';


--
-- Name: order_item_id_seq; Type: SEQUENCE; Schema: shop; Owner: migrator
--

ALTER TABLE shop.order_item ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME shop.order_item_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: orders; Type: TABLE; Schema: shop; Owner: migrator
--

CREATE TABLE shop.orders (
    id integer NOT NULL,
    user_id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    promocode_id integer,
    discount_per_order numeric(12,2) DEFAULT 0 NOT NULL,
    CONSTRAINT orders_check CHECK (((promocode_id IS NOT NULL) OR (discount_per_order = (0)::numeric))),
    CONSTRAINT orders_discount_per_order_check CHECK ((discount_per_order >= (0)::numeric)),
    CONSTRAINT orders_status_check CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'confirmed'::character varying, 'cancelled'::character varying])::text[])))
);


ALTER TABLE shop.orders OWNER TO migrator;

--
-- Name: COLUMN orders.promocode_id; Type: COMMENT; Schema: shop; Owner: migrator
--

COMMENT ON COLUMN shop.orders.promocode_id IS 'NULL = без промокода';


--
-- Name: COLUMN orders.discount_per_order; Type: COMMENT; Schema: shop; Owner: migrator
--

COMMENT ON COLUMN shop.orders.discount_per_order IS 'Скидка, зафиксированная в заказе';


--
-- Name: orders_id_seq; Type: SEQUENCE; Schema: shop; Owner: migrator
--

ALTER TABLE shop.orders ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME shop.orders_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: payments; Type: TABLE; Schema: shop; Owner: migrator
--

CREATE TABLE shop.payments (
    id integer NOT NULL,
    order_id integer NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    paid_at timestamp with time zone,
    CONSTRAINT payments_check CHECK ((((status)::text = 'succeeded'::text) = (paid_at IS NOT NULL))),
    CONSTRAINT payments_status_check CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'succeeded'::character varying, 'failed'::character varying])::text[])))
);


ALTER TABLE shop.payments OWNER TO migrator;

--
-- Name: COLUMN payments.created_at; Type: COMMENT; Schema: shop; Owner: migrator
--

COMMENT ON COLUMN shop.payments.created_at IS 'Начало попытки оплаты';


--
-- Name: COLUMN payments.paid_at; Type: COMMENT; Schema: shop; Owner: migrator
--

COMMENT ON COLUMN shop.payments.paid_at IS 'Момент, когда деньги пришли';


--
-- Name: payments_id_seq; Type: SEQUENCE; Schema: shop; Owner: migrator
--

ALTER TABLE shop.payments ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME shop.payments_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: promocodes; Type: TABLE; Schema: shop; Owner: migrator
--

CREATE TABLE shop.promocodes (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    discount_sum numeric(12,2) NOT NULL,
    CONSTRAINT promocodes_discount_sum_check CHECK ((discount_sum > (0)::numeric))
);


ALTER TABLE shop.promocodes OWNER TO migrator;

--
-- Name: COLUMN promocodes.discount_sum; Type: COMMENT; Schema: shop; Owner: migrator
--

COMMENT ON COLUMN shop.promocodes.discount_sum IS 'Текущая скидка, ₸';


--
-- Name: promocodes_id_seq; Type: SEQUENCE; Schema: shop; Owner: migrator
--

ALTER TABLE shop.promocodes ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME shop.promocodes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: refunds; Type: TABLE; Schema: shop; Owner: migrator
--

CREATE TABLE shop.refunds (
    id integer NOT NULL,
    order_item_id integer NOT NULL,
    quantity integer NOT NULL,
    reason character varying(255),
    refunded_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT refunds_quantity_check CHECK ((quantity > 0))
);


ALTER TABLE shop.refunds OWNER TO migrator;

--
-- Name: refunds_id_seq; Type: SEQUENCE; Schema: shop; Owner: migrator
--

ALTER TABLE shop.refunds ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME shop.refunds_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: users; Type: TABLE; Schema: shop; Owner: migrator
--

CREATE TABLE shop.users (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    surname character varying(100) NOT NULL,
    birthdate date,
    city character varying(100),
    registered_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE shop.users OWNER TO migrator;

--
-- Name: COLUMN users.birthdate; Type: COMMENT; Schema: shop; Owner: migrator
--

COMMENT ON COLUMN shop.users.birthdate IS 'Клиент может не указать';


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: shop; Owner: migrator
--

ALTER TABLE shop.users ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME shop.users_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: authors authors_pkey; Type: CONSTRAINT; Schema: shop; Owner: migrator
--

ALTER TABLE ONLY shop.authors
    ADD CONSTRAINT authors_pkey PRIMARY KEY (id);


--
-- Name: book_author book_author_pkey; Type: CONSTRAINT; Schema: shop; Owner: migrator
--

ALTER TABLE ONLY shop.book_author
    ADD CONSTRAINT book_author_pkey PRIMARY KEY (book_id, author_id);


--
-- Name: books books_pkey; Type: CONSTRAINT; Schema: shop; Owner: migrator
--

ALTER TABLE ONLY shop.books
    ADD CONSTRAINT books_pkey PRIMARY KEY (id);


--
-- Name: genres genres_name_key; Type: CONSTRAINT; Schema: shop; Owner: migrator
--

ALTER TABLE ONLY shop.genres
    ADD CONSTRAINT genres_name_key UNIQUE (name);


--
-- Name: genres genres_pkey; Type: CONSTRAINT; Schema: shop; Owner: migrator
--

ALTER TABLE ONLY shop.genres
    ADD CONSTRAINT genres_pkey PRIMARY KEY (id);


--
-- Name: order_item order_item_order_id_book_id_key; Type: CONSTRAINT; Schema: shop; Owner: migrator
--

ALTER TABLE ONLY shop.order_item
    ADD CONSTRAINT order_item_order_id_book_id_key UNIQUE (order_id, book_id);


--
-- Name: order_item order_item_pkey; Type: CONSTRAINT; Schema: shop; Owner: migrator
--

ALTER TABLE ONLY shop.order_item
    ADD CONSTRAINT order_item_pkey PRIMARY KEY (id);


--
-- Name: orders orders_pkey; Type: CONSTRAINT; Schema: shop; Owner: migrator
--

ALTER TABLE ONLY shop.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (id);


--
-- Name: payments payments_pkey; Type: CONSTRAINT; Schema: shop; Owner: migrator
--

ALTER TABLE ONLY shop.payments
    ADD CONSTRAINT payments_pkey PRIMARY KEY (id);


--
-- Name: promocodes promocodes_name_key; Type: CONSTRAINT; Schema: shop; Owner: migrator
--

ALTER TABLE ONLY shop.promocodes
    ADD CONSTRAINT promocodes_name_key UNIQUE (name);


--
-- Name: promocodes promocodes_pkey; Type: CONSTRAINT; Schema: shop; Owner: migrator
--

ALTER TABLE ONLY shop.promocodes
    ADD CONSTRAINT promocodes_pkey PRIMARY KEY (id);


--
-- Name: refunds refunds_pkey; Type: CONSTRAINT; Schema: shop; Owner: migrator
--

ALTER TABLE ONLY shop.refunds
    ADD CONSTRAINT refunds_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: shop; Owner: migrator
--

ALTER TABLE ONLY shop.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_book_author_author_id; Type: INDEX; Schema: shop; Owner: migrator
--

CREATE INDEX ix_book_author_author_id ON shop.book_author USING btree (author_id);


--
-- Name: ix_books_genre_id; Type: INDEX; Schema: shop; Owner: migrator
--

CREATE INDEX ix_books_genre_id ON shop.books USING btree (genre_id);


--
-- Name: ix_order_item_book_id; Type: INDEX; Schema: shop; Owner: migrator
--

CREATE INDEX ix_order_item_book_id ON shop.order_item USING btree (book_id);


--
-- Name: ix_orders_user_id; Type: INDEX; Schema: shop; Owner: migrator
--

CREATE INDEX ix_orders_user_id ON shop.orders USING btree (user_id);


--
-- Name: ix_payments_order_id; Type: INDEX; Schema: shop; Owner: migrator
--

CREATE INDEX ix_payments_order_id ON shop.payments USING btree (order_id);


--
-- Name: ix_payments_paid_at; Type: INDEX; Schema: shop; Owner: migrator
--

CREATE INDEX ix_payments_paid_at ON shop.payments USING btree (paid_at);


--
-- Name: ix_refunds_order_item_id; Type: INDEX; Schema: shop; Owner: migrator
--

CREATE INDEX ix_refunds_order_item_id ON shop.refunds USING btree (order_item_id);


--
-- Name: ix_refunds_refunded_at; Type: INDEX; Schema: shop; Owner: migrator
--

CREATE INDEX ix_refunds_refunded_at ON shop.refunds USING btree (refunded_at);


--
-- Name: uq_payments_one_succeeded_per_order; Type: INDEX; Schema: shop; Owner: migrator
--

CREATE UNIQUE INDEX uq_payments_one_succeeded_per_order ON shop.payments USING btree (order_id) WHERE ((status)::text = 'succeeded'::text);


--
-- Name: book_author book_author_author_id_fkey; Type: FK CONSTRAINT; Schema: shop; Owner: migrator
--

ALTER TABLE ONLY shop.book_author
    ADD CONSTRAINT book_author_author_id_fkey FOREIGN KEY (author_id) REFERENCES shop.authors(id);


--
-- Name: book_author book_author_book_id_fkey; Type: FK CONSTRAINT; Schema: shop; Owner: migrator
--

ALTER TABLE ONLY shop.book_author
    ADD CONSTRAINT book_author_book_id_fkey FOREIGN KEY (book_id) REFERENCES shop.books(id);


--
-- Name: books books_genre_id_fkey; Type: FK CONSTRAINT; Schema: shop; Owner: migrator
--

ALTER TABLE ONLY shop.books
    ADD CONSTRAINT books_genre_id_fkey FOREIGN KEY (genre_id) REFERENCES shop.genres(id);


--
-- Name: order_item order_item_book_id_fkey; Type: FK CONSTRAINT; Schema: shop; Owner: migrator
--

ALTER TABLE ONLY shop.order_item
    ADD CONSTRAINT order_item_book_id_fkey FOREIGN KEY (book_id) REFERENCES shop.books(id);


--
-- Name: order_item order_item_order_id_fkey; Type: FK CONSTRAINT; Schema: shop; Owner: migrator
--

ALTER TABLE ONLY shop.order_item
    ADD CONSTRAINT order_item_order_id_fkey FOREIGN KEY (order_id) REFERENCES shop.orders(id);


--
-- Name: orders orders_promocode_id_fkey; Type: FK CONSTRAINT; Schema: shop; Owner: migrator
--

ALTER TABLE ONLY shop.orders
    ADD CONSTRAINT orders_promocode_id_fkey FOREIGN KEY (promocode_id) REFERENCES shop.promocodes(id);


--
-- Name: orders orders_user_id_fkey; Type: FK CONSTRAINT; Schema: shop; Owner: migrator
--

ALTER TABLE ONLY shop.orders
    ADD CONSTRAINT orders_user_id_fkey FOREIGN KEY (user_id) REFERENCES shop.users(id);


--
-- Name: payments payments_order_id_fkey; Type: FK CONSTRAINT; Schema: shop; Owner: migrator
--

ALTER TABLE ONLY shop.payments
    ADD CONSTRAINT payments_order_id_fkey FOREIGN KEY (order_id) REFERENCES shop.orders(id);


--
-- Name: refunds refunds_order_item_id_fkey; Type: FK CONSTRAINT; Schema: shop; Owner: migrator
--

ALTER TABLE ONLY shop.refunds
    ADD CONSTRAINT refunds_order_item_id_fkey FOREIGN KEY (order_item_id) REFERENCES shop.order_item(id);


--
-- Name: SCHEMA app; Type: ACL; Schema: -; Owner: migrator
--

GRANT USAGE ON SCHEMA app TO app_service;


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: pg_database_owner
--

REVOKE USAGE ON SCHEMA public FROM PUBLIC;


--
-- Name: SCHEMA shop; Type: ACL; Schema: -; Owner: migrator
--

GRANT USAGE ON SCHEMA shop TO llm_readonly;


--
-- Name: TABLE authors; Type: ACL; Schema: shop; Owner: migrator
--

GRANT SELECT ON TABLE shop.authors TO llm_readonly;


--
-- Name: TABLE book_author; Type: ACL; Schema: shop; Owner: migrator
--

GRANT SELECT ON TABLE shop.book_author TO llm_readonly;


--
-- Name: TABLE books; Type: ACL; Schema: shop; Owner: migrator
--

GRANT SELECT ON TABLE shop.books TO llm_readonly;


--
-- Name: TABLE genres; Type: ACL; Schema: shop; Owner: migrator
--

GRANT SELECT ON TABLE shop.genres TO llm_readonly;


--
-- Name: TABLE order_item; Type: ACL; Schema: shop; Owner: migrator
--

GRANT SELECT ON TABLE shop.order_item TO llm_readonly;


--
-- Name: TABLE orders; Type: ACL; Schema: shop; Owner: migrator
--

GRANT SELECT ON TABLE shop.orders TO llm_readonly;


--
-- Name: TABLE payments; Type: ACL; Schema: shop; Owner: migrator
--

GRANT SELECT ON TABLE shop.payments TO llm_readonly;


--
-- Name: TABLE promocodes; Type: ACL; Schema: shop; Owner: migrator
--

GRANT SELECT ON TABLE shop.promocodes TO llm_readonly;


--
-- Name: TABLE refunds; Type: ACL; Schema: shop; Owner: migrator
--

GRANT SELECT ON TABLE shop.refunds TO llm_readonly;


--
-- Name: TABLE users; Type: ACL; Schema: shop; Owner: migrator
--

GRANT SELECT ON TABLE shop.users TO llm_readonly;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: app; Owner: migrator
--

ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA app GRANT SELECT,USAGE ON SEQUENCES TO app_service;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: app; Owner: migrator
--

ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA app GRANT SELECT,INSERT,DELETE,UPDATE ON TABLES TO app_service;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: shop; Owner: migrator
--

ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA shop GRANT SELECT ON TABLES TO llm_readonly;


--
-- PostgreSQL database dump complete
--

\unrestrict bookstore

